# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""golem-framework — LLM framework abstraction, agentic loop, and LLM Gateway.

Public surface
--------------
Loop
    AgentLoop       Abstract base class — every concrete loop must implement this.
    LangGraphLoop   Built-in ReAct loop backed by LangGraph (provider-agnostic).

LLM Gateway
    LLMClient       Abstract base class for LLM provider adapters.
    build_llm_client  Factory — selects the correct client from provider/protocol config.

Supporting utilities
    SkillLoader     Reads Persona (AGENTS.md) and Skills (skills/*.md) at startup.
    BUILTIN_TOOLS   Registry mapping tool names to BaseTool instances.
    resolve_builtin_tools  Helper to resolve a list of names to BaseTool objects.
"""

from .llm_gateway.base import LLMClient
from .llm_gateway.factory import build_llm_client
from .loop.base import AgentLoop
from .loop.langgraph import LangGraphLoop
from .skill_loader import SkillLoader
from .tool_registry import BUILTIN_TOOLS, resolve_builtin_tools

__all__ = [
    # Loop
    "AgentLoop",
    "LangGraphLoop",
    # LLM Gateway
    "LLMClient",
    "build_llm_client",
    # Utilities
    "SkillLoader",
    "BUILTIN_TOOLS",
    "resolve_builtin_tools",
]
