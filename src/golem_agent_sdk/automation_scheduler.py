# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Background Automation scheduler for the Golem Agent Runner.

Supports three trigger types inside an Automation:
  CronTrigger     — fires on a 5-field UTC cron expression (requires ``croniter``).
  TimerTrigger    — fires every ``interval_seconds``.
  WebhookTrigger  — registered as a live FastAPI route; fires on HTTP POST.

Usage
-----
    scheduler = AutomationScheduler(executor)
    scheduler.register(Automation(
        trigger=CronTrigger(cron="*/5 * * * *"),
        task_input="health check",
    ))
    # in FastAPI lifespan:
    await scheduler.start(app)
    ...
    await scheduler.stop()
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from golem_agent_sdk.models import (
    Automation,
    CronTrigger,
    TimerTrigger,
    WebhookTrigger,
)
from golem_agent_sdk.store import TaskStore

logger = logging.getLogger("runner.scheduler")


class AutomationScheduler:
    """In-process scheduler that drives Cron, Timer, and Webhook automations.

    Args:
        executor:   Callable that accepts an instruction string and returns the
                    agent's reply (the same adapter used by the A2A router).
        task_store: Shared TaskStore so automation-fired tasks appear in
                    GET /a2a/tasks.
    """

    def __init__(self, executor: Callable[[str], str], task_store: TaskStore) -> None:
        self._executor = executor
        self._task_store = task_store
        self._automations: dict[str, Automation] = {}
        self._loop_tasks: dict[str, asyncio.Task] = {}  # timer/cron asyncio tasks
        self._app = None  # FastAPI app reference; set in start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, automation: Automation) -> None:
        """Add an automation to the scheduler's registry.

        Args:
            automation: The automation to register.
        """
        self._automations[automation.automation_id] = automation
        logger.info("Automation registered: id=%s type=%s", automation.automation_id, automation.trigger.type)

    def remove(self, automation_id: str) -> bool:
        """Remove and stop an automation.

        Args:
            automation_id: The ID of the automation to remove.

        Returns:
            True if the automation was found and removed, False otherwise.
        """
        if automation_id not in self._automations:
            return False
        task = self._loop_tasks.pop(automation_id, None)
        if task:
            task.cancel()
        del self._automations[automation_id]
        logger.info("Automation removed: id=%s", automation_id)
        return True

    def list_all(self) -> list[Automation]:
        """Return all registered automations."""
        return list(self._automations.values())

    def get(self, automation_id: str) -> Automation | None:
        """Return an automation by ID, or None if not found."""
        return self._automations.get(automation_id)

    async def start(self, app) -> None:  # noqa: ANN001
        """Start all registered automations and mount webhook routes.

        Must be called inside the FastAPI lifespan after the app is ready.

        Args:
            app: The FastAPI application instance (needed to add webhook routes).
        """
        self._app = app
        for automation in list(self._automations.values()):
            await self._start_automation(automation)

    async def stop(self) -> None:
        """Cancel all running asyncio loop tasks."""
        for task in self._loop_tasks.values():
            task.cancel()
        if self._loop_tasks:
            await asyncio.gather(*self._loop_tasks.values(), return_exceptions=True)
        self._loop_tasks.clear()
        logger.info("AutomationScheduler stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _start_automation(self, automation: Automation) -> None:
        """Dispatch to the appropriate start method based on trigger type."""
        if not automation.enabled:
            logger.info("Automation %s is disabled — skipping start", automation.automation_id)
            return
        if isinstance(automation.trigger, CronTrigger):
            self._loop_tasks[automation.automation_id] = asyncio.create_task(
                self._cron_loop(automation), name=f"cron-{automation.automation_id}"
            )
        elif isinstance(automation.trigger, TimerTrigger):
            self._loop_tasks[automation.automation_id] = asyncio.create_task(
                self._timer_loop(automation), name=f"timer-{automation.automation_id}"
            )
        elif isinstance(automation.trigger, WebhookTrigger):
            self._mount_webhook(automation)

    def _fire(self, task_input: str, automation_id: str, source: str = "manual") -> None:
        """Execute the instruction and record the result in the task store.

        Args:
            task_input:    The instruction string to send to the agent.
            automation_id: The ID of the automation that fired (for logging).
            source:        Origin label stored on the task (e.g. 'timer', 'cron', 'webhook').
        """
        from golem_agent_sdk.models import A2ATask, TaskStatus

        task = A2ATask(message=task_input, source=source)
        task.status = TaskStatus.WORKING
        self._task_store.add(task)
        logger.info("Automation %s fired — task %s submitted", automation_id, task.task_id)
        try:
            reply = self._executor(task_input)
            task.status = TaskStatus.COMPLETED
            task.result = reply
        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.result = str(exc)
            logger.warning("Automation %s task %s failed: %s", automation_id, task.task_id, exc)
        task.updated_at = datetime.now(UTC)

    async def _timer_loop(self, automation: Automation) -> None:
        """Repeat every ``interval_seconds`` until cancelled."""
        assert isinstance(automation.trigger, TimerTrigger)  # noqa: S101
        interval = automation.trigger.interval_seconds
        logger.info("Timer automation %s started (interval=%ds)", automation.automation_id, interval)
        try:
            while True:
                await asyncio.sleep(interval)
                current = self._automations.get(automation.automation_id)
                if current is None or not current.enabled:
                    continue
                await asyncio.to_thread(self._fire, current.task_input, automation.automation_id, "timer")
        except asyncio.CancelledError:
            logger.info("Timer automation %s cancelled", automation.automation_id)

    async def _cron_loop(self, automation: Automation) -> None:
        """Sleep until the next cron tick, fire, then repeat."""
        assert isinstance(automation.trigger, CronTrigger)  # noqa: S101
        try:
            from croniter import croniter  # type: ignore[import-untyped]
        except ImportError:
            logger.error(
                "croniter is not installed — cron automation %s will not fire. "
                "Add 'croniter' to your dependencies.",
                automation.automation_id,
            )
            return

        logger.info("Cron automation %s started (cron='%s')", automation.automation_id, automation.trigger.cron)
        try:
            while True:
                now = datetime.now(UTC).timestamp()
                cron = croniter(automation.trigger.cron, now)
                next_ts: float = cron.get_next(float)
                sleep_secs = max(0.0, next_ts - datetime.now(UTC).timestamp())
                await asyncio.sleep(sleep_secs)
                current = self._automations.get(automation.automation_id)
                if current is None or not current.enabled:
                    continue
                await asyncio.to_thread(self._fire, current.task_input, automation.automation_id, "cron")
        except asyncio.CancelledError:
            logger.info("Cron automation %s cancelled", automation.automation_id)

    def _mount_webhook(self, automation: Automation) -> None:
        """Dynamically add a POST route for the webhook automation.

        The route accepts an arbitrary JSON body and passes it (serialised)
        into the task_input template via ``{body}``.

        Args:
            automation: The automation whose trigger is a WebhookTrigger.
        """
        assert isinstance(automation.trigger, WebhookTrigger)  # noqa: S101
        if self._app is None:
            logger.warning("Cannot mount webhook automation %s — app not set", automation.automation_id)
            return

        from fastapi import Request
        from fastapi.routing import APIRoute

        automation_id = automation.automation_id
        task_input_template = automation.task_input
        fire = self._fire
        path = automation.trigger.path

        async def _webhook_handler(request: Request) -> dict:
            current = self._automations.get(automation_id)
            if current is None or not current.enabled:
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail=f"Automation {automation_id} is disabled or removed.")
            try:
                body = await request.body()
                body_str = body.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body_str = ""
            task_input = task_input_template.replace("{body}", body_str)
            await asyncio.to_thread(fire, task_input, automation_id, "webhook")
            return {"status": "accepted", "automation_id": automation_id}

        route = APIRoute(
            path=path,
            endpoint=_webhook_handler,
            methods=["POST"],
            name=f"webhook_{automation_id}",
        )
        self._app.router.routes.append(route)
        logger.info("Webhook automation %s mounted at POST %s", automation_id, path)
