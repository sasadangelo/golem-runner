# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""golem-agent-sdk — A2A identity, task lifecycle, and platform integration.

Deliberately framework-agnostic: no LLM dependency, importable by any runner
regardless of the agentic backend (LangGraph, AutoGen, pure A2A proxy…).
"""

from .models import A2ATask, TaskStatus
from .router import a2a_router
from .store import TaskStore

__all__ = [
    "A2ATask",
    "TaskStatus",
    "TaskStore",
    "a2a_router",
]
