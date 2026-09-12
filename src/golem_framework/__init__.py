# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""golem-framework — LLM framework abstraction, agentic loop, and skill loading.

This package provides the AgentLoop abstraction over LLM agentic backends
(currently LangGraph + WatsonX) so the runner remains framework-agnostic.

Public surface
--------------
Loop
    AgentLoop       Abstract base class — every concrete loop must implement this.
    LangGraphLoop   Built-in ReAct loop backed by LangGraph + WatsonX (MVP 1).

Supporting utilities
    SkillLoader     Reads Persona (AGENTS.md) and Skills (skills/*.md) at startup.
    ToolRegistry    Maps built-in tool names to BaseTool instances.
    resolve_builtin_tools  Helper to resolve a list of tool names to BaseTool objects.

Planned (Phase 3)
    AutoGenLoop     AutoGen-backed loop.
    CrewAILoop      CrewAI-backed loop.
"""

from .loop.base import AgentLoop
from .loop.langgraph import LangGraphLoop
from .skill_loader import SkillLoader
from .tool_registry import BUILTIN_TOOLS, resolve_builtin_tools

__all__ = [
    "AgentLoop",
    "LangGraphLoop",
    "SkillLoader",
    "BUILTIN_TOOLS",
    "resolve_builtin_tools",
]
