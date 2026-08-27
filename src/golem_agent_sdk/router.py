# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""FastAPI router for A2A inbound task endpoints and background trigger management.

This router is mounted by the runner's main.py.  It owns:

  A2A task lifecycle:
    POST /a2a/tasks/send       receive an inbound task, execute it, return result
    GET  /a2a/tasks/{task_id}  query a single task
    GET  /a2a/tasks            list all tasks

  Background triggers (Cron, Timer, Webhook):
    POST   /a2a/triggers       register a new trigger
    GET    /a2a/triggers        list all triggers
    GET    /a2a/triggers/{id}   get a single trigger
    DELETE /a2a/triggers/{id}   remove a trigger

The router receives an ``executor`` callable and a ``TriggerScheduler`` instance
at mount time so it stays completely decoupled from LangGraph.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from golem_agent_sdk.models import A2ATask, CronTrigger, TimerTrigger, TriggerConfig, WebhookTrigger

from .models import TaskStatus
from .store import TaskStore
from .trigger_scheduler import TriggerScheduler

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
    source: str = "manual"


class A2ATaskResponse(BaseModel):
    """Response shape returned by all A2A task endpoints."""

    id: str
    status: dict[str, Any]
    artifacts: list[dict[str, Any]]


class TaskStatusResponse(BaseModel):
    """Response shape for GET /a2a/tasks/{task_id}."""

    task_id: str
    status: str
    source: str = "manual"
    message: str
    result: str | None = None
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Trigger response schema
# ---------------------------------------------------------------------------


class TriggerResponse(BaseModel):
    """Response shape for trigger endpoints."""

    id: str
    type: str
    enabled: bool
    message: str
    # type-specific fields (optional)
    cron: str | None = None
    interval_seconds: int | None = None
    path: str | None = None


def _trigger_to_response(t: TriggerConfig) -> TriggerResponse:
    base = TriggerResponse(id=t.id, type=t.type, enabled=t.enabled, message=t.message)
    if isinstance(t, CronTrigger):
        base.cron = t.cron
    elif isinstance(t, TimerTrigger):
        base.interval_seconds = t.interval_seconds
    elif isinstance(t, WebhookTrigger):
        base.path = t.path
    return base


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_a2a_router(
    executor: Callable[[str], str],
    scheduler: TriggerScheduler | None = None,
) -> APIRouter:
    """Return an APIRouter with A2A task endpoints and trigger management.

    Args:
        executor:  A callable that takes an instruction string and returns the
                   agent's reply string.  Injected by the runner at startup.
        scheduler: Optional TriggerScheduler instance.  When provided, the
                   /a2a/triggers endpoints are exposed.

    Returns:
        A configured FastAPI APIRouter ready to be included in the main app.
    """
    router = APIRouter(prefix="/a2a", tags=["a2a"])

    # ------------------------------------------------------------------
    # A2A task lifecycle endpoints
    # ------------------------------------------------------------------

    @router.post("/tasks/send", response_model=A2ATaskResponse)
    async def tasks_send(params: A2ASendRequest) -> A2ATaskResponse:
        """
        Receive an inbound A2A task, execute it, and return the result.

        Lifecycle: submitted → working → completed / failed.

        Args:
            params: The A2A task request with an optional task ID and a message.
        """
        text: str = next(
            (p.text for p in params.message.parts if p.type == "text" and p.text),
            "",
        )
        if not text:
            raise HTTPException(status_code=400, detail="No text part found in A2A message.")

        task: A2ATask = A2ATask(
            task_id=params.id or f"task-{uuid.uuid4().hex[:12]}",
            message=text,
            status=TaskStatus.SUBMITTED,
            source=params.source,
        )
        task_store.add(task)

        task.status = TaskStatus.WORKING
        task.updated_at = datetime.now(UTC)

        try:
            reply: str = executor(text)
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.result = str(exc)
            task.updated_at = datetime.now(UTC)
            raise HTTPException(status_code=500, detail=str(exc)) from exc

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

        Args:
            task_id: The unique task identifier.
        """
        task: A2ATask | None = task_store.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
        return TaskStatusResponse(
            task_id=task.task_id,
            status=task.status,
            source=task.source,
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
                source=t.source,
                message=t.message,
                result=t.result,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in task_store.list_all()
        ]

    # ------------------------------------------------------------------
    # Trigger management endpoints  (only when a scheduler is provided)
    # ------------------------------------------------------------------

    if scheduler is not None:

        @router.post("/triggers", response_model=TriggerResponse, status_code=201)
        async def create_trigger(
            trigger: Annotated[CronTrigger | TimerTrigger | WebhookTrigger, Body(discriminator="type")],
        ) -> TriggerResponse:
            """
            Register a new background trigger.

            Accepts ``type: cron``, ``type: timer``, or ``type: webhook``.

            Args:
                trigger: The trigger configuration.
            """
            scheduler.register(trigger)
            await scheduler._start_trigger(trigger)  # noqa: SLF001
            return _trigger_to_response(trigger)

        @router.get("/triggers", response_model=list[TriggerResponse])
        async def list_triggers() -> list[TriggerResponse]:
            """Return all registered triggers."""
            return [_trigger_to_response(t) for t in scheduler.list_all()]

        @router.get("/triggers/{trigger_id}", response_model=TriggerResponse)
        async def get_trigger(trigger_id: str) -> TriggerResponse:
            """
            Return a single trigger by ID.

            Args:
                trigger_id: The unique trigger identifier.
            """
            t = scheduler.get(trigger_id)
            if t is None:
                raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found.")
            return _trigger_to_response(t)

        @router.delete("/triggers/{trigger_id}", status_code=204)
        async def delete_trigger(trigger_id: str) -> None:
            """
            Remove and stop a trigger.

            Args:
                trigger_id: The unique trigger identifier.
            """
            if not scheduler.remove(trigger_id):
                raise HTTPException(status_code=404, detail=f"Trigger {trigger_id} not found.")

    return router


# ---------------------------------------------------------------------------
# Default router (placeholder — overridden in main.py with real executor)
# ---------------------------------------------------------------------------

a2a_router: APIRouter = APIRouter()
