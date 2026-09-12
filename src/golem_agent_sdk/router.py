# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""FastAPI router for A2A inbound task endpoints and Automation management.

This router is mounted by the runner's main.py.  It owns:

  A2A task lifecycle:
    POST /a2a/tasks/send          receive an inbound task, execute it, return result
    GET  /a2a/tasks/{task_id}     query a single task
    GET  /a2a/tasks               list all tasks

  Automation management (Cron, Timer, Webhook):
    POST   /a2a/automations       register a new automation
    GET    /a2a/automations       list all automations
    GET    /a2a/automations/{id}  get a single automation
    DELETE /a2a/automations/{id}  remove an automation

The router receives an ``executor`` callable and an ``AutomationScheduler``
instance at mount time so it stays completely decoupled from LangGraph.
"""

from __future__ import annotations

import asyncio
import uuid
from asyncio.events import AbstractEventLoop
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from golem_agent_sdk.models import (
    Automation,
    CronTrigger,
    TimerTrigger,
    WebhookTrigger,
)

from .automation_scheduler import AutomationScheduler
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
# Automation response schema
# ---------------------------------------------------------------------------


class AutomationResponse(BaseModel):
    """Response shape for Automation endpoints."""

    automation_id: str
    name: str
    enabled: bool
    task_input: str
    # trigger type
    trigger_type: str
    # type-specific fields (optional)
    cron: str | None = None
    interval_seconds: int | None = None
    path: str | None = None


def _automation_to_response(a: Automation) -> AutomationResponse:
    """Convert an Automation domain object to its API response shape."""
    resp = AutomationResponse(
        automation_id=a.automation_id,
        name=a.name,
        enabled=a.enabled,
        task_input=a.task_input,
        trigger_type=a.trigger.type,
    )
    if isinstance(a.trigger, CronTrigger):
        resp.cron = a.trigger.cron
    elif isinstance(a.trigger, TimerTrigger):
        resp.interval_seconds = a.trigger.interval_seconds
    elif isinstance(a.trigger, WebhookTrigger):
        resp.path = a.trigger.path
    return resp


# ---------------------------------------------------------------------------
# Automation creation request schema
# ---------------------------------------------------------------------------


class _CronAutomationRequest(BaseModel):
    """Create request for a cron-based automation."""

    name: str = ""
    task_input: str
    trigger: CronTrigger


class _TimerAutomationRequest(BaseModel):
    """Create request for a timer-based automation."""

    name: str = ""
    task_input: str
    trigger: TimerTrigger


class _WebhookAutomationRequest(BaseModel):
    """Create request for a webhook-based automation."""

    name: str = ""
    task_input: str
    trigger: WebhookTrigger


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------


def build_a2a_router(
    executor: Callable[[str], str],
    scheduler: AutomationScheduler | None = None,
) -> APIRouter:
    """Return an APIRouter with A2A task endpoints and Automation management.

    Args:
        executor:  A callable that takes an instruction string and returns the
                   agent's reply string.  Injected by the runner at startup.
        scheduler: Optional AutomationScheduler instance.  When provided, the
                   /a2a/automations endpoints are exposed.

    Returns:
        A configured FastAPI APIRouter ready to be included in the main app.
    """
    router = APIRouter(prefix="/a2a", tags=["a2a"])

    # ------------------------------------------------------------------
    # A2A task lifecycle endpoints
    # ------------------------------------------------------------------

    @router.post(path="/tasks/send", response_model=A2ATaskResponse, status_code=200)
    async def tasks_send(params: A2ASendRequest) -> A2ATaskResponse:
        """Receive an inbound A2A task, execute it and return the result.

        The executor runs in a thread pool so the event loop is never blocked.
        The response is returned only when execution completes or fails.
        The task record is always stored so GET /a2a/tasks/{id} reflects the
        final state immediately after this call returns.

        Lifecycle: working → completed / failed.

        Args:
            params: The A2A task request with an optional task ID and a message.
        """
        text: str = next(
            (p.text for p in params.message.parts if p.type == "text" and p.text),
            "",
        )
        if not text:
            raise HTTPException(status_code=400, detail="No text part found in A2A message.")

        from golem_agent_sdk.models import A2ATask

        task: A2ATask = A2ATask(
            task_id=params.id or f"task-{uuid.uuid4().hex[:12]}",
            message=text,
            status=TaskStatus.WORKING,
            source=params.source,
        )
        task_store.add(task)

        loop: AbstractEventLoop = asyncio.get_event_loop()
        try:
            reply: str = await loop.run_in_executor(None, executor, text)
            task.status = TaskStatus.COMPLETED
            task.result = reply
        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.result = str(exc)
            task.updated_at = datetime.now(tz=UTC)
            raise HTTPException(status_code=500, detail=task.result) from exc
        finally:
            task.updated_at = datetime.now(tz=UTC)

        return A2ATaskResponse(
            id=task.task_id,
            status={"state": TaskStatus.COMPLETED},
            artifacts=[{"parts": [{"type": "text", "text": reply}]}],
        )

    @router.get(path="/tasks/{task_id}", response_model=TaskStatusResponse)
    async def get_task(task_id: str) -> TaskStatusResponse:
        """Return the current lifecycle state of an A2A task.

        Args:
            task_id: The unique task identifier.
        """
        from golem_agent_sdk.models import A2ATask

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
    # Automation management endpoints  (only when a scheduler is provided)
    # ------------------------------------------------------------------

    if scheduler is not None:

        @router.post(path="/automations", response_model=AutomationResponse, status_code=201)
        async def create_automation(
            body: Annotated[
                _CronAutomationRequest | _TimerAutomationRequest | _WebhookAutomationRequest,
                Body(),
            ],
        ) -> AutomationResponse:
            """Register a new background Automation.

            The request body must include a ``trigger`` object with
            ``type: cron``, ``type: timer``, or ``type: webhook``, plus a
            ``task_input`` string and an optional ``name``.

            Args:
                body: The automation creation request.
            """
            automation = Automation(
                name=body.name,
                trigger=body.trigger,
                task_input=body.task_input,
            )
            scheduler.register(automation)
            await scheduler._start_automation(automation)  # noqa: SLF001
            return _automation_to_response(automation)

        @router.get(path="/automations", response_model=list[AutomationResponse])
        async def list_automations() -> list[AutomationResponse]:
            """Return all registered automations."""
            return [_automation_to_response(a) for a in scheduler.list_all()]

        @router.get(path="/automations/{automation_id}", response_model=AutomationResponse)
        async def get_automation(automation_id: str) -> AutomationResponse:
            """Return a single automation by ID.

            Args:
                automation_id: The unique automation identifier.
            """
            a: Automation | None = scheduler.get(automation_id)
            if a is None:
                raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found.")
            return _automation_to_response(a)

        @router.delete(path="/automations/{automation_id}", status_code=204)
        async def delete_automation(automation_id: str) -> None:
            """Remove and stop an automation.

            Args:
                automation_id: The unique automation identifier.
            """
            if not scheduler.remove(automation_id):
                raise HTTPException(status_code=404, detail=f"Automation {automation_id} not found.")

    return router


# ---------------------------------------------------------------------------
# Default router (placeholder — overridden in main.py with real executor)
# ---------------------------------------------------------------------------

a2a_router: APIRouter = APIRouter()
