# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Golem Agent Runner — FastAPI application exposing A2A and chat endpoints."""

import logging
import logging.config
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from agent import build_agent
from core.config import settings
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from golem_agent_sdk.router import build_a2a_router, task_store
from golem_agent_sdk.trigger_scheduler import TriggerScheduler

# ---------------------------------------------------------------------------
# Logging — configure all runner.* loggers to appear in stdout alongside uvicorn
# ---------------------------------------------------------------------------

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(levelname)s:     %(name)s - %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "runner": {"handlers": ["console"], "level": "INFO", "propagate": False},
        },
    }
)

logger = logging.getLogger("runner.main")

# ---------------------------------------------------------------------------
# LangGraph recursion limit — max tool-call hops per turn
# ---------------------------------------------------------------------------

_RECURSION_LIMIT: int = 50

# ---------------------------------------------------------------------------
# A2A Agent Card — served at /.well-known/agent.json (A2A v1.0 spec)
# ---------------------------------------------------------------------------

_enabled_skills: list[str] = [s.strip() for s in settings.agent.enabled_skills.split(",") if s.strip()]

AGENT_CARD: dict[str, Any] = {
    "id": settings.agent.id,
    "name": settings.agent.name,
    "description": settings.agent.description,
    "version": "0.1.0",
    "endpoint": settings.agent.endpoint,
    "capabilities": {
        "streaming": True,
        "pushNotifications": False,
    },
    "skills": [{"id": skill, "name": skill} for skill in _enabled_skills],
}


# ---------------------------------------------------------------------------
# Startup handshake — register Agent Card with the Control Plane broker
# ---------------------------------------------------------------------------


async def _register_with_control_plane(card: dict[str, Any]) -> None:
    """Push the Agent Card to the Control Plane via POST /agents/{id}/handshake.

    Skipped silently when ``settings.agent.cp_url`` is empty (local dev mode).
    Logs a warning on failure but never blocks the runner startup.
    """
    if not settings.agent.cp_url:
        return
    url = f"{settings.agent.cp_url.rstrip('/')}/agents/{settings.agent.id}/handshake"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"card": card})
            response.raise_for_status()
        logger.info("Handshake completed with Control Plane at %s", settings.agent.cp_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Handshake with Control Plane failed (will rely on pull): %s", exc)


# ---------------------------------------------------------------------------
# MCP tool loading — connect to all configured MCP servers at boot
# ---------------------------------------------------------------------------


async def _load_mcp_tools() -> list[BaseTool]:
    """Connect to each MCP server in ``settings.agent.mcp_servers`` and
    collect their tools.

    Returns an empty list when no MCP servers are configured or when all
    servers are unreachable (failures are logged as warnings).
    """
    mcp_logger = logging.getLogger("runner.mcp")

    servers = settings.agent.mcp_servers
    if not servers:
        mcp_logger.info("No MCP servers configured — starting with built-in tools only")
        return []

    from langchain_mcp_adapters.client import MultiServerMCPClient

    connections: dict[str, Any] = {}
    for i, srv in enumerate(servers):
        entry: dict[str, Any] = {"url": srv.url, "transport": "streamable_http"}
        resolved = srv.resolved_headers()
        if resolved:
            entry["headers"] = resolved
        connections[f"mcp_{i}"] = entry

    mcp_logger.info("Connecting to %d MCP server(s): %s", len(servers), [s.url for s in servers])

    tools: list[BaseTool] = []
    try:
        mcp_client = MultiServerMCPClient(connections)
        tools = await mcp_client.get_tools()
        mcp_logger.info(
            "Loaded %d MCP tool(s) from %d server(s): %s",
            len(tools),
            len(servers),
            [t.name for t in tools],
        )
    except BaseException as exc:  # noqa: BLE001
        # anyio raises BaseExceptionGroup (a BaseException subclass, not Exception)
        # when a TaskGroup task fails, so a plain `except Exception` misses it.
        if isinstance(exc, BaseExceptionGroup):
            causes = "; ".join(f"{type(e).__name__}: {e}" for e in exc.exceptions)
            mcp_logger.warning(
                "Failed to load MCP tools (runner will start without them): %s — causes: [%s]",
                exc,
                causes,
            )
        else:
            mcp_logger.warning(
                "Failed to load MCP tools (runner will start without them): %s",
                exc,
                exc_info=exc,
            )

    return tools


# ---------------------------------------------------------------------------
# Lifespan: MCP boot + handshake + trigger scheduler
# ---------------------------------------------------------------------------

# Module-level reference; set during lifespan so all endpoint handlers share it.
agent_executor: CompiledStateGraph | None = None

# Module-level scheduler; set during lifespan so the router can reference it.
trigger_scheduler: TriggerScheduler | None = None


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan: load MCP tools, compile agent, start triggers, handshake."""
    global agent_executor, trigger_scheduler  # noqa: PLW0603

    mcp_tools = await _load_mcp_tools()
    agent_executor = build_agent(mcp_tools=mcp_tools)
    logger.info("Agent compiled — built-in tools + %d MCP tool(s)", len(mcp_tools))

    await _register_with_control_plane(AGENT_CARD)

    # Start background trigger scheduler
    trigger_scheduler = TriggerScheduler(executor=_langgraph_executor, task_store=task_store)
    _seed_triggers_from_config(trigger_scheduler)
    await trigger_scheduler.start(app_)
    logger.info("TriggerScheduler started with %d trigger(s)", len(trigger_scheduler.list_all()))

    try:
        yield
    finally:
        await trigger_scheduler.stop()


def _seed_triggers_from_config(scheduler: TriggerScheduler) -> None:
    """Register triggers declared in config.yaml under ``agent.triggers``.

    Each entry must have a ``type`` field (``cron``, ``timer``, or ``webhook``).
    Invalid entries are logged as warnings and skipped.
    """
    from golem_agent_sdk.models import CronTrigger, TimerTrigger, WebhookTrigger

    triggers_cfg = getattr(settings.agent, "triggers", None) or []
    for raw in triggers_cfg:
        try:
            trigger_type = raw.get("type") if isinstance(raw, dict) else None
            if trigger_type == "cron":
                scheduler.register(CronTrigger(**raw))
            elif trigger_type == "timer":
                scheduler.register(TimerTrigger(**raw))
            elif trigger_type == "webhook":
                scheduler.register(WebhookTrigger(**raw))
            else:
                logger.warning("Unknown trigger type in config: %s — skipping", raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Invalid trigger config %s — skipping: %s", raw, exc)


app: FastAPI = FastAPI(title="Golem Agent Runner", version="0.1.0", lifespan=lifespan)


@app.middleware(middleware_type="http")
async def well_known_middleware(request: Request, call_next: Any) -> Response:
    """Serve /.well-known/agent.json before Starlette routing drops the request."""
    if request.url.path == "/.well-known/agent.json":
        return JSONResponse(content=AGENT_CARD)
    return await call_next(request)


# ---------------------------------------------------------------------------
# A2A router (including trigger endpoints)
# ---------------------------------------------------------------------------


def _langgraph_executor(text: str) -> str:
    """Adapter: wrap agent_executor.invoke() to match the SDK's str → str contract."""
    assert agent_executor is not None, "agent_executor not initialised"  # noqa: S101
    inputs: dict[str, list[HumanMessage]] = {"messages": [HumanMessage(content=text)]}
    result = agent_executor.invoke(inputs, config={"recursion_limit": _RECURSION_LIMIT})
    return str(result["messages"][-1].content)


# Build the router with a deferred scheduler reference so the router is
# registered during module import (before lifespan runs) yet uses the
# scheduler that is set inside lifespan.
def _get_scheduler() -> TriggerScheduler | None:
    return trigger_scheduler


# We mount the router immediately; the scheduler is None at import time but
# will be set in lifespan before any request can reach the trigger endpoints.
# We pass a proxy that always reads the module-level variable.
class _SchedulerProxy:
    """Lazy proxy forwarding all attribute access to the module-level scheduler."""

    def __getattr__(self, name: str) -> Any:
        if trigger_scheduler is None:
            raise RuntimeError("TriggerScheduler not initialised yet.")
        return getattr(trigger_scheduler, name)


_scheduler_proxy = _SchedulerProxy()

app.include_router(build_a2a_router(_langgraph_executor, scheduler=_scheduler_proxy))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------


class ChatPayload(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post(path="/chat", response_model=ChatResponse)
async def chat(payload: ChatPayload) -> ChatResponse:
    assert agent_executor is not None, "agent_executor not initialised"  # noqa: S101
    try:
        inputs: dict[str, list[HumanMessage]] = {"messages": [HumanMessage(content=payload.message)]}
        result = agent_executor.invoke(inputs, config={"recursion_limit": _RECURSION_LIMIT})
        last_message = result["messages"][-1]
        return ChatResponse(reply=str(last_message.content))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.websocket(path="/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    assert agent_executor is not None, "agent_executor not initialised"  # noqa: S101
    await websocket.accept()
    history: list[BaseMessage] = []
    try:
        while True:
            user_message: str = await websocket.receive_text()
            logger.info("WS chat message received (%d chars)", len(user_message))
            history.append(HumanMessage(content=user_message))
            inputs: dict[str, list[BaseMessage]] = {"messages": history}
            reply_tokens: list[str] = []
            tool_calls_made: int = 0
            try:
                async for event in agent_executor.astream_events(
                    inputs,
                    version="v2",
                    config={"recursion_limit": _RECURSION_LIMIT},
                ):
                    kind = event["event"]
                    if kind == "on_tool_start":
                        tool_calls_made += 1
                        logger.info("Tool call: %s  args=%s", event["name"], event["data"].get("input"))
                    elif kind == "on_tool_end":
                        output = str(event["data"].get("output", ""))[:200]
                        logger.info("Tool result: %s  → %s", event["name"], output)
                    elif kind == "on_chat_model_stream":
                        chunk = event["data"].get("chunk")
                        if chunk is None:
                            continue
                        token = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if token:
                            reply_tokens.append(token)
                            await websocket.send_text(token)
                if not reply_tokens and tool_calls_made > 0:
                    await websocket.send_text("✅ Done.")
                    reply_tokens = ["✅ Done."]
                await websocket.send_text(data="[DONE]")
                history.append(AIMessage(content="".join(reply_tokens)))
                logger.info("Turn complete — %d tokens streamed", len(reply_tokens))
            except Exception as e:
                history.pop()
                await websocket.send_text(data=f"[ERROR] {e}")
                logger.error("Agent error during turn: %s", e)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")


@app.get(path="/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
