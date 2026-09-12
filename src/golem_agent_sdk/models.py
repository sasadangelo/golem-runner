# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""A2A task lifecycle and Automation domain models for golem-agent-sdk.

Domain alignment
----------------
``Automation``  — the entity the user creates and manages (has identity,
                  lifecycle, enabled flag).
``Trigger``     — value object embedded inside an Automation that carries
                  only the *firing rule* (when to fire, not what to do).

The three concrete trigger types are:
  CronTrigger     — fires on a 5-field UTC cron expression.
  TimerTrigger    — fires every ``interval_seconds``.
  WebhookTrigger  — fires on an HTTP POST to a dynamic route.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# A2A task lifecycle
# ---------------------------------------------------------------------------


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
# Trigger value objects — the *firing rule* embedded inside an Automation
# ---------------------------------------------------------------------------


class CronTrigger(BaseModel):
    """Schedule an Automation on a cron expression (UTC)."""

    type: Literal["cron"] = "cron"
    cron: str = Field(description="Standard 5-field cron expression in UTC, e.g. '*/30 * * * *'.")


class TimerTrigger(BaseModel):
    """Fire an Automation after a fixed interval, then repeat every interval_seconds."""

    type: Literal["timer"] = "timer"
    interval_seconds: int = Field(gt=0, description="Seconds between each firing.")


class WebhookTrigger(BaseModel):
    """Expose an HTTP endpoint that fires an Automation on POST."""

    type: Literal["webhook"] = "webhook"
    path: str = Field(description="URL path suffix, e.g. '/webhooks/github'. Must start with '/'.")


# Union type used by Automation.trigger and the scheduler
TriggerConfig = CronTrigger | TimerTrigger | WebhookTrigger


# ---------------------------------------------------------------------------
# Automation entity
# ---------------------------------------------------------------------------


class Automation(BaseModel):
    """A background automation rule attached to an Agent.

    Fires a task on the agent according to its Trigger (cron, timer, or
    webhook) without requiring human input.

    Attributes:
        automation_id: Stable unique identifier for this automation.
        name:          Human-readable label (e.g. "health-check every 30s").
        trigger:       The firing rule — a CronTrigger, TimerTrigger, or
                       WebhookTrigger value object.
        task_input:    The instruction text sent to the agent when the
                       automation fires.
        enabled:       Set to False to pause the automation without deleting it.
    """

    automation_id: str = Field(default_factory=lambda: f"auto-{uuid.uuid4().hex[:8]}")
    name: str = Field(default="", description="Human-readable label for this automation.")
    trigger: CronTrigger | TimerTrigger | WebhookTrigger = Field(
        description="The firing rule — discriminated by the 'type' field.",
    )
    task_input: str = Field(description="Instruction text passed to the agent when the automation fires.")
    enabled: bool = Field(default=True, description="Set to false to pause without deleting.")
