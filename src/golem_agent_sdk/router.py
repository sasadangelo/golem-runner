# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""FastAPI router for A2A inbound task endpoints.

This router is mounted by the runner's main.py.  It owns the full A2A task
lifecycle: a task arrives at ``POST /a2a/tasks/send``, transitions through
``submitted → working → completed / failed``, and is queryable at any point.

The router receives an ``executor`` callable at mount time so it stays
completely decoupled from LangGraph — any callable that accepts a string and
returns a string can be injected (including test mocks).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from golem_agent_sdk.models import A2ATask

from .models import TaskStatus
from .store import TaskStore

# ---------------------------------------------------------------------------
# Shared task store — one instance per process, injected into the router at
# startup so tests can replace it with a fresh one.
# ---------------------------------------------------------------------------
task_store: TaskStore = TaskStore()


# ---------------------------------------------------------------------------
# Wire schemas  (A2A v1.0 message shape)
# ---------------------------------------------------------------------------


class _A2AMessagePart(BaseModel):
    type: str
    text: str = ""


class _A2AMessage(BaseModel):
    role: str
    parts: list[_A2AMessagePart]


class A2ASendRequest(BaseModel):
    """Inbound A2A task request (A2A v1.0 tasks/send)."""

    id: str | None = None
    message: _A2AMessage


class A2ATaskResponse(BaseModel):
    """Response shape returned by all A2A task endpoints."""

    id: str
    status: dict[str, Any]
    artifacts: list[dict[str, Any]]


class TaskStatusResponse(BaseModel):
    """Response shape for GET /a2a/tasks/{task_id}."""

    task_id: str
    status: str
    message: str
    result: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_a2a_router(executor: Callable[[str], str]) -> APIRouter:
    """Return an APIRouter with all A2A task endpoints bound to *executor*.

    Args:
        executor: A callable that takes an instruction string and returns the
                  agent's reply string.  Injected by the runner at startup so
                  the SDK never imports LangGraph or any LLM library directly.

    Returns:
        A configured FastAPI APIRouter ready to be included in the main app.
    """
    router = APIRouter(prefix="/a2a", tags=["a2a"])

    @router.post("/tasks/send", response_model=A2ATaskResponse)
    async def tasks_send(params: A2ASendRequest) -> A2ATaskResponse:
        """
        Receive an inbound A2A task, execute it, and return the result.

        Lifecycle: submitted → working → completed / failed.
        The task record is persisted in the TaskStore throughout and is
        queryable via GET /a2a/tasks/{task_id}.

        Args:
            params: The A2A task request with an optional task ID and a message.
        """
        # --- extract text -----------------------------------------------
        text: str = next(
            (p.text for p in params.message.parts if p.type == "text" and p.text),
            "",
        )
        if not text:
            raise HTTPException(status_code=400, detail="No text part found in A2A message.")

        # --- create record: submitted -----------------------------------
        task: A2ATask = A2ATask(
            task_id=params.id or f"task-{uuid.uuid4().hex[:12]}",
            message=text,
            status=TaskStatus.SUBMITTED,
        )
        task_store.add(task)

        # --- transition: working ----------------------------------------
        task.status = TaskStatus.WORKING
        task.updated_at = datetime.now(UTC)

        # --- execute via injected executor ------------------------------
        try:
            reply: str = executor(text)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.result = str(exc)
            task.updated_at = datetime.now(UTC)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        # --- transition: completed --------------------------------------
        task.status = TaskStatus.COMPLETED
        task.result = reply
        task.updated_at = datetime.now(UTC)

        return A2ATaskResponse(
            id=task.task_id,
            status={"state": TaskStatus.COMPLETED},
            artifacts=[{"parts": [{"type": "text", "text": reply}]}],
        )

    @router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
    async def get_task(task_id: str) -> TaskStatusResponse:
        """
        Return the current lifecycle state of an A2A task.

        Useful for the Control Plane to poll task progress and for the
        future ``golem agent tasks`` CLI command.

        Args:
            task_id: The unique task identifier.
        """
        task: A2ATask | None = task_store.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
        return TaskStatusResponse(
            task_id=task.task_id,
            status=task.status,
            message=task.message,
            result=task.result,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @router.get(path="/tasks", response_model=list[TaskStatusResponse])
    async def list_tasks() -> list[TaskStatusResponse]:
        """Return all A2A tasks received by this runner instance."""
        return [
            TaskStatusResponse(
                task_id=t.task_id,
                status=t.status,
                message=t.message,
                result=t.result,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in task_store.list_all()
        ]

    return router


# ---------------------------------------------------------------------------
# Default router (placeholder — overridden in main.py with real executor)
# ---------------------------------------------------------------------------

a2a_router: APIRouter = APIRouter()
