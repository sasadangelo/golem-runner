# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""A2A task lifecycle domain models for golem-agent-sdk."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

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
    result: str | None = Field(default=None, description="Output produced when the task completes.")
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
