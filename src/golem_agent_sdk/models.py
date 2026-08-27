# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""A2A task lifecycle domain models for golem-agent-sdk."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class TaskStatus(StrEnum):
    """Lifecycle states of an A2A task (A2A v1.0)."""

    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"


class A2ATask(BaseModel):
    """An inbound A2A task received by the runner from a peer agent or the Control Plane."""

    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:12]}")
    message: str = Field(default="", description="The instruction text for this task.")
    status: TaskStatus = TaskStatus.SUBMITTED
    source: str = Field(
        default="manual",
        description="Origin of the task: 'golem-cli', 'timer', 'cron', 'webhook', or 'a2a'.",
    )
    result: str | None = Field(default=None, description="Output produced when the task completes.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


# ---------------------------------------------------------------------------
# Background trigger models (Cron, Timer, Webhook)
# ---------------------------------------------------------------------------


class CronTrigger(BaseModel):
    """Schedule a task on a cron expression (UTC)."""

    type: Literal["cron"] = "cron"
    id: str = Field(default_factory=lambda: f"trig-{uuid.uuid4().hex[:8]}")
    cron: str = Field(description="Standard 5-field cron expression in UTC, e.g. '*/30 * * * *'.")
    message: str = Field(description="Instruction text passed to the agent when the trigger fires.")
    enabled: bool = Field(default=True, description="Set to false to pause without deleting.")


class TimerTrigger(BaseModel):
    """Fire a task after a fixed delay, then repeat every interval_seconds."""

    type: Literal["timer"] = "timer"
    id: str = Field(default_factory=lambda: f"trig-{uuid.uuid4().hex[:8]}")
    interval_seconds: int = Field(gt=0, description="Seconds between each firing.")
    message: str = Field(description="Instruction text passed to the agent when the trigger fires.")
    enabled: bool = Field(default=True, description="Set to false to pause without deleting.")


class WebhookTrigger(BaseModel):
    """Expose an HTTP endpoint that fires a task on POST."""

    type: Literal["webhook"] = "webhook"
    id: str = Field(default_factory=lambda: f"trig-{uuid.uuid4().hex[:8]}")
    path: str = Field(description="URL path suffix, e.g. '/webhooks/github'. Must start with '/'.")
    message: str = Field(description="Instruction template; use {body} to inject the raw request body.")
    enabled: bool = Field(default=True, description="Set to false to pause without deleting.")


# Union type used in the router / scheduler
TriggerConfig = CronTrigger | TimerTrigger | WebhookTrigger
