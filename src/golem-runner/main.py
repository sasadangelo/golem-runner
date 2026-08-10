# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Golem Agent Runner — FastAPI application exposing A2A and chat endpoints."""

from typing import Any

from agent import agent_executor as agent_executor
from core.config import settings
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel

from golem_agent_sdk.router import build_a2a_router

app: FastAPI = FastAPI(title="Golem Agent Runner", version="0.1.0")

# ---------------------------------------------------------------------------
# A2A Agent Card — served at /.well-known/agent.json (A2A v1.0 spec)
# ---------------------------------------------------------------------------

_enabled_skills: list[str] = [s.strip() for s in settings.agent.enabled_skill.split(",") if s.strip()]

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


# Starlette blocks paths with dot-prefixed segments (e.g. /.well-known/) via its
# routing internals, so we intercept the request with a middleware before routing.
@app.middleware(middleware_type="http")
async def well_known_middleware(request: Request, call_next: Any) -> Response:
    """Serve /.well-known/agent.json before Starlette routing drops the request."""
    if request.url.path == "/.well-known/agent.json":
        return JSONResponse(content=AGENT_CARD)
    return await call_next(request)


# ---------------------------------------------------------------------------
# A2A router — mounted from golem-agent-sdk
#
# The executor adapter bridges the LangGraph agent_executor (golem-framework
# concern) to the plain callable interface expected by the SDK router.
# ---------------------------------------------------------------------------


def _langgraph_executor(text: str) -> str:
    """Adapter: wrap agent_executor.invoke() to match the SDK's str → str contract."""
    inputs: dict[str, list[HumanMessage]] = {"messages": [HumanMessage(content=text)]}
    result = agent_executor.invoke(inputs)
    return str(result["messages"][-1].content)


app.include_router(build_a2a_router(_langgraph_executor))


# ---------------------------------------------------------------------------
# Chat endpoint (human-facing)
# ---------------------------------------------------------------------------


class ChatPayload(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post(path="/chat", response_model=ChatResponse)
async def chat(payload: ChatPayload) -> ChatResponse:
    try:
        inputs: dict[str, list[HumanMessage]] = {"messages": [HumanMessage(content=payload.message)]}
        result = agent_executor.invoke(inputs)
        last_message = result["messages"][-1]
        return ChatResponse(reply=str(last_message.content))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.websocket(path="/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    history: list[BaseMessage] = []
    try:
        while True:
            user_message: str = await websocket.receive_text()
            history.append(HumanMessage(content=user_message))
            inputs: dict[str, list[BaseMessage]] = {"messages": history}
            reply_tokens: list[str] = []
            try:
                async for event in agent_executor.astream_events(inputs, version="v2"):
                    if event["event"] == "on_chat_model_stream":
                        chunk = event["data"].get("chunk")
                        if chunk is None:
                            continue
                        token = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if token:
                            reply_tokens.append(token)
                            await websocket.send_text(token)
                await websocket.send_text(data="[DONE]")
                history.append(AIMessage(content="".join(reply_tokens)))
            except Exception as e:
                history.pop()  # rimuove il HumanMessage se la risposta è fallita
                await websocket.send_text(data=f"[ERROR] {e}")
    except WebSocketDisconnect:
        pass


@app.get(path="/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
