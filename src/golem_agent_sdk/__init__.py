# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""golem-agent-sdk — A2A identity, task lifecycle, and platform integration.

Deliberately framework-agnostic: no LLM dependency, importable by any runner
regardless of the agentic backend (LangGraph, AutoGen, pure A2A proxy…).

Public surface
--------------
Agent Card
    AgentCard           Pydantic model representing the A2A v1.0 Agent Card.
    AgentCapabilities   Capability flags (streaming, pushNotifications).
    AgentTools          Built-in and MCP tools advertised in the card.
    ToolEntry           A single tool entry (id + name).
    build_agent_card    Factory function to construct an AgentCard at startup.

Handshake
    perform_handshake   Async helper to push the Agent Card to the Control Plane.

A2A task lifecycle
    A2ATask             Domain model for an inbound A2A task.
    TaskStatus          Lifecycle states (submitted, working, completed, failed).
    TaskStore           In-memory registry of A2A tasks.

Background triggers
    CronTrigger         Fire a task on a cron expression.
    TimerTrigger        Fire a task every N seconds.
    WebhookTrigger      Expose an HTTP POST endpoint that fires a task.
    TriggerConfig       Union type for all trigger kinds.
    TriggerScheduler    In-process scheduler for Cron, Timer, and Webhook triggers.

FastAPI router
    a2a_router          Default placeholder router (replaced at startup).
    build_a2a_router    Factory that wires executor + scheduler into an APIRouter.
"""

from .card import AgentCapabilities, AgentCard, AgentTools, ToolEntry, build_agent_card
from .handshake import perform_handshake
from .models import A2ATask, CronTrigger, TaskStatus, TimerTrigger, TriggerConfig, WebhookTrigger
from .router import a2a_router, build_a2a_router
from .store import TaskStore
from .trigger_scheduler import TriggerScheduler

__all__ = [
    # Agent Card
    "AgentCapabilities",
    "AgentCard",
    "AgentTools",
    "ToolEntry",
    "build_agent_card",
    # Handshake
    "perform_handshake",
    # A2A task lifecycle
    "A2ATask",
    "TaskStatus",
    "TaskStore",
    # Triggers
    "CronTrigger",
    "TimerTrigger",
    "TriggerConfig",
    "TriggerScheduler",
    "WebhookTrigger",
    # Router
    "a2a_router",
    "build_a2a_router",
]
