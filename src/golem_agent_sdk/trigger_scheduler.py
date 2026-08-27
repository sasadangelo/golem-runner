# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Background trigger scheduler for the Golem Agent Runner.

Supports three trigger types:
  - CronTrigger  — fires on a 5-field UTC cron expression (requires ``croniter``).
  - TimerTrigger — fires every ``interval_seconds``.
  - WebhookTrigger — registered as a live FastAPI route; fires on HTTP POST.

Usage
-----
    scheduler = TriggerScheduler(executor)
    scheduler.register(CronTrigger(cron="*/5 * * * *", message="health check"))
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

from golem_agent_sdk.models import CronTrigger, TimerTrigger, TriggerConfig, WebhookTrigger
from golem_agent_sdk.store import TaskStore

logger = logging.getLogger("runner.scheduler")


class TriggerScheduler:
    """In-process scheduler that drives Cron, Timer, and Webhook triggers.

    Args:
        executor: Callable that accepts an instruction string and returns the
                  agent's reply (the same adapter used by the A2A router).
        task_store: Shared TaskStore so triggered tasks appear in GET /a2a/tasks.
    """

    def __init__(self, executor: Callable[[str], str], task_store: TaskStore) -> None:
        self._executor = executor
        self._task_store = task_store
        self._triggers: dict[str, TriggerConfig] = {}
        self._loop_tasks: dict[str, asyncio.Task] = {}  # timer/cron asyncio tasks
        self._app = None  # FastAPI app reference; set in start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def register(self, trigger: TriggerConfig) -> None:
        """Add a trigger to the scheduler's registry.

        Args:
            trigger: The trigger to register.
        """
        self._triggers[trigger.id] = trigger
        logger.info("Trigger registered: id=%s type=%s", trigger.id, trigger.type)

    def remove(self, trigger_id: str) -> bool:
        """Remove and stop a trigger.

        Args:
            trigger_id: The ID of the trigger to remove.

        Returns:
            True if the trigger was found and removed, False otherwise.
        """
        if trigger_id not in self._triggers:
            return False
        # Cancel background asyncio task if running
        task = self._loop_tasks.pop(trigger_id, None)
        if task:
            task.cancel()
        del self._triggers[trigger_id]
        logger.info("Trigger removed: id=%s", trigger_id)
        return True

    def list_all(self) -> list[TriggerConfig]:
        """Return all registered triggers."""
        return list(self._triggers.values())

    def get(self, trigger_id: str) -> TriggerConfig | None:
        """Return a trigger by ID, or None if not found."""
        return self._triggers.get(trigger_id)

    async def start(self, app) -> None:  # noqa: ANN001
        """Start all registered triggers and mount webhook routes.

        Must be called inside the FastAPI lifespan after the app is ready.

        Args:
            app: The FastAPI application instance (needed to add webhook routes).
        """
        self._app = app
        for trigger in list(self._triggers.values()):
            await self._start_trigger(trigger)

    async def stop(self) -> None:
        """Cancel all running asyncio loop tasks."""
        for task in self._loop_tasks.values():
            task.cancel()
        if self._loop_tasks:
            await asyncio.gather(*self._loop_tasks.values(), return_exceptions=True)
        self._loop_tasks.clear()
        logger.info("TriggerScheduler stopped")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _start_trigger(self, trigger: TriggerConfig) -> None:
        """Dispatch to the appropriate start method based on trigger type."""
        if not trigger.enabled:
            logger.info("Trigger %s is disabled — skipping start", trigger.id)
            return
        if isinstance(trigger, CronTrigger):
            self._loop_tasks[trigger.id] = asyncio.create_task(
                self._cron_loop(trigger), name=f"cron-{trigger.id}"
            )
        elif isinstance(trigger, TimerTrigger):
            self._loop_tasks[trigger.id] = asyncio.create_task(
                self._timer_loop(trigger), name=f"timer-{trigger.id}"
            )
        elif isinstance(trigger, WebhookTrigger):
            self._mount_webhook(trigger)

    def _fire(self, message: str, trigger_id: str, source: str = "manual") -> None:
        """Execute the instruction and record the result in the task store.

        Args:
            message:    The instruction string to send to the agent.
            trigger_id: The ID of the trigger that fired (for logging).
            source:     Origin label stored on the task (e.g. 'timer', 'cron', 'webhook').
        """
        from datetime import UTC, datetime

        from golem_agent_sdk.models import A2ATask, TaskStatus

        task = A2ATask(message=message, source=source)
        task.status = TaskStatus.WORKING
        self._task_store.add(task)
        logger.info("Trigger %s fired — task %s submitted", trigger_id, task.task_id)
        try:
            reply = self._executor(message)
            task.status = TaskStatus.COMPLETED
            task.result = reply
        except Exception as exc:  # noqa: BLE001
            task.status = TaskStatus.FAILED
            task.result = str(exc)
            logger.warning("Trigger %s task %s failed: %s", trigger_id, task.task_id, exc)
        task.updated_at = datetime.now(UTC)

    async def _timer_loop(self, trigger: TimerTrigger) -> None:
        """Repeat every ``interval_seconds`` until cancelled."""
        logger.info("Timer trigger %s started (interval=%ds)", trigger.id, trigger.interval_seconds)
        try:
            while True:
                await asyncio.sleep(trigger.interval_seconds)
                current = self._triggers.get(trigger.id)
                if current is None or not current.enabled:
                    continue
                await asyncio.to_thread(self._fire, trigger.message, trigger.id, "timer")
        except asyncio.CancelledError:
            logger.info("Timer trigger %s cancelled", trigger.id)

    async def _cron_loop(self, trigger: CronTrigger) -> None:
        """Sleep until the next cron tick, fire, then repeat."""
        try:
            from croniter import croniter  # type: ignore[import-untyped]
        except ImportError:
            logger.error(
                "croniter is not installed — cron trigger %s will not fire. "
                "Add 'croniter' to your dependencies.",
                trigger.id,
            )
            return

        logger.info("Cron trigger %s started (cron='%s')", trigger.id, trigger.cron)
        try:
            while True:
                now = datetime.now(UTC).timestamp()
                cron = croniter(trigger.cron, now)
                next_ts: float = cron.get_next(float)
                sleep_secs = max(0.0, next_ts - datetime.now(UTC).timestamp())
                await asyncio.sleep(sleep_secs)
                current = self._triggers.get(trigger.id)
                if current is None or not current.enabled:
                    continue
                await asyncio.to_thread(self._fire, trigger.message, trigger.id, "cron")
        except asyncio.CancelledError:
            logger.info("Cron trigger %s cancelled", trigger.id)

    def _mount_webhook(self, trigger: WebhookTrigger) -> None:
        """Dynamically add a POST route for the webhook trigger.

        The route accepts an arbitrary JSON body and passes it (serialised) into
        the message template via ``{body}``.

        Args:
            trigger: The webhook trigger configuration.
        """
        if self._app is None:
            logger.warning("Cannot mount webhook %s — app not set", trigger.id)
            return

        from fastapi import Request
        from fastapi.routing import APIRoute

        trigger_id = trigger.id
        message_template = trigger.message
        fire = self._fire

        async def _webhook_handler(request: Request) -> dict:
            current = self._triggers.get(trigger_id)
            if current is None or not current.enabled:
                from fastapi import HTTPException
                raise HTTPException(status_code=404, detail=f"Webhook {trigger_id} is disabled or removed.")
            try:
                body = await request.body()
                body_str = body.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body_str = ""
            message = message_template.replace("{body}", body_str)
            await asyncio.to_thread(fire, message, trigger_id, "webhook")
            return {"status": "accepted", "trigger_id": trigger_id}

        route = APIRoute(
            path=trigger.path,
            endpoint=_webhook_handler,
            methods=["POST"],
            name=f"webhook_{trigger.id}",
        )
        self._app.router.routes.append(route)
        logger.info("Webhook trigger %s mounted at POST %s", trigger.id, trigger.path)
