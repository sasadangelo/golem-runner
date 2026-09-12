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

from agent import build_agent
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from core.config import MCPServerConfig, settings
from golem_agent_sdk.card import AgentCard, build_agent_card
from golem_agent_sdk.handshake import perform_handshake
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

# Built once at module load with values from config; mcp section is completed
# in lifespan after MCP connections are established.
agent_card: AgentCard = build_agent_card(
    agent_id=settings.agent.id,
    name=settings.agent.name,
    description=settings.agent.description,
    endpoint=settings.agent.endpoint,
    builtin_tools=settings.agent.builtin_tools,
)


# ---------------------------------------------------------------------------
# MCP tool loading — connect to all configured MCP servers at boot
# ---------------------------------------------------------------------------


async def _load_mcp_tools() -> list[BaseTool]:
    """Load the tools exposed by MCP servers configured under ``agent.mcp_servers``.

    Returns an empty list when no MCP servers are configured or when all
    servers are unreachable (failures are logged as warnings).
    """
    mcp_logger = logging.getLogger(name="runner.mcp")

    # ``mcp_servers`` comes from the runner configuration, not from the agent graph.
    servers: list[MCPServerConfig] = settings.agent.mcp_servers
    if not servers:
        mcp_logger.info(msg="No MCP servers configured — starting with built-in tools only")
        return []

    # Adapt every configured server to the MultiServerMCPClient connection format.
    # Headers are resolved here so secrets/config references never reach the graph.
    connections: dict[str, Any] = {}
    for i, srv in enumerate(servers):
        entry: dict[str, Any] = {"url": srv.url, "transport": "streamable_http"}
        resolved: dict[str, str] = srv.resolved_headers()
        if resolved:
            entry["headers"] = resolved
        connections[f"mcp_{i}"] = entry

    mcp_logger.info("Connecting to %d MCP server(s): %s", len(servers), [s.url for s in servers])

    tools: list[BaseTool] = []
    try:
        # Connect asynchronously and convert each remote MCP tool into a LangChain BaseTool.
        mcp_client: MultiServerMCPClient = MultiServerMCPClient(connections)
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

# ---------------------------------------------------------------------------
# Conversation history store — keyed by conversation_id (str).
# The special key "" holds the legacy implicit single-conversation history.
# ---------------------------------------------------------------------------
_conversation_histories: dict[str, list[BaseMessage]] = {}


@asynccontextmanager
async def lifespan(app_: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan: load MCP tools, compile agent, start triggers, handshake."""
    global agent_executor, trigger_scheduler, agent_card  # noqa: PLW0603

    mcp_tools: list[BaseTool] = await _load_mcp_tools()
    agent_executor = build_agent(mcp_tools=mcp_tools)
    logger.info("Agent compiled — built-in tools + %d MCP tool(s)", len(mcp_tools))

    # Populate the MCP section of the Agent Card now that tools are known.
    agent_card = agent_card.with_mcp_tools([t.name for t in mcp_tools])

    await perform_handshake(
        cp_url=settings.agent.cp_url,
        agent_id=settings.agent.id,
        card=agent_card.to_dict(),
    )

    # Start background trigger scheduler
    trigger_scheduler = TriggerScheduler(executor=_langgraph_executor, task_store=task_store)
    _seed_triggers_from_config(scheduler=trigger_scheduler)
    await trigger_scheduler.start(app=app_)
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
        return JSONResponse(content=agent_card.to_dict())
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


_scheduler_proxy: _SchedulerProxy = _SchedulerProxy()

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
async def ws_chat(websocket: WebSocket, conversation_id: str | None = None) -> None:
    """Handle a streaming WebSocket chat session.

    When ``conversation_id`` is provided the message history for that
    conversation is reused across connections, keeping each conversation
    isolated from others.  Without a ``conversation_id`` the legacy implicit
    single-history behaviour is preserved (key ``""`` in the store).

    Args:
        websocket:       The inbound WebSocket connection.
        conversation_id: Optional UUID forwarded by the Control Plane proxy.
    """
    assert agent_executor is not None, "agent_executor not initialised"  # noqa: S101
    # Complete the WebSocket handshake before receiving or sending messages.
    await websocket.accept()

    # Resolve the history bucket — "" is the legacy implicit conversation.
    history_key: str = conversation_id or ""
    history: list[BaseMessage] = _conversation_histories.setdefault(history_key, [])

    logger.info(
        "WS chat session opened — conversation_id=%s  history_len=%d",
        conversation_id or "<implicit>",
        len(history),
    )

    try:
        # Keep the connection open so one client can send multiple chat turns.
        while True:
            user_message: str = await websocket.receive_text()
            logger.info("WS chat message received (%d chars)", len(user_message))

            # Give the graph the complete conversation, including this new turn.
            history.append(HumanMessage(content=user_message))
            inputs: dict[str, list[BaseMessage]] = {"messages": history}
            reply_tokens: list[str] = []
            tool_calls_made: int = 0
            try:
                # Run the complete LangGraph agent loop. It may invoke tools and
                # make multiple model calls; events arrive as each step progresses.
                async for event in agent_executor.astream_events(
                    inputs,
                    version="v2",
                    config={"recursion_limit": _RECURSION_LIMIT},
                ):
                    kind: str = event["event"]
                    if kind == "on_tool_start":
                        # Tool activity is recorded server-side, not sent to the client.
                        tool_calls_made += 1
                        logger.info("Tool call: %s  args=%s", event["name"], event["data"].get("input"))
                    elif kind == "on_tool_end":
                        output = str(event["data"].get("output", ""))[:200]
                        logger.info("Tool result: %s  → %s", event["name"], output)
                    elif kind == "on_chat_model_stream":
                        # Forward each model text chunk immediately over the WebSocket.
                        chunk = event["data"].get("chunk")
                        if chunk is None:
                            continue
                        token = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if token:
                            reply_tokens.append(token)
                            await websocket.send_text(token)

                # Some tool-only runs emit no model text; still give the client a reply.
                if not reply_tokens and tool_calls_made > 0:
                    await websocket.send_text("✅ Done.")
                    reply_tokens = ["✅ Done."]

                # Mark the stream boundary and persist the reply for the next turn.
                await websocket.send_text(data="[DONE]")
                history.append(AIMessage(content="".join(reply_tokens)))
                logger.info("Turn complete — %d tokens streamed", len(reply_tokens))
            except Exception as e:
                # Discard the unprocessed user message to preserve a consistent history.
                history.pop()
                await websocket.send_text(data=f"[ERROR] {e}")
                logger.error("Agent error during turn: %s", e)
    except WebSocketDisconnect:
        logger.info(
            "WebSocket disconnected — conversation_id=%s",
            conversation_id or "<implicit>",
        )


@app.get(path="/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
