# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Thin entrypoint — builds a LangGraphLoop from the runner configuration.

All agentic logic lives in ``golem_framework``.  This module only reads
``core.config.settings`` and calls the framework factory.
"""

import logging

from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph

from core.config import settings
from golem_framework import LangGraphLoop, SkillLoader, resolve_builtin_tools
from golem_framework.llm_gateway import LLMClient, build_llm_client

logger = logging.getLogger("runner.agent")


def build_agent(mcp_tools: list[BaseTool] | None = None) -> CompiledStateGraph:
    """Build and compile the LangGraph agent loop used by every chat turn.

    Selects the LLM provider/protocol from config (``llm.provider`` +
    ``llm.protocol``), resolves built-in tools, then delegates graph
    construction entirely to ``LangGraphLoop``.

    Args:
        mcp_tools: Optional list of LangChain tools loaded from MCP servers
                   at boot time by ``main._load_mcp_tools``.

    Returns:
        A compiled LangGraph state machine ready for ``.invoke()`` and
        ``.astream_events()``.
    """
    llm_client: LLMClient = build_llm_client(
        provider=settings.llm.provider,
        protocol=settings.llm.protocol,
        model=settings.llm.model,
        url=settings.llm.url,
        api_key=settings.llm.api_key.get_secret_value() if settings.llm.api_key else None,
        project_id=settings.llm.project_id,
        max_new_tokens=settings.llm.max_new_tokens,
    )

    builtin = resolve_builtin_tools(settings.agent.builtin_tools)
    if mcp_tools:
        logger.info("Received %d MCP tool(s): %s", len(mcp_tools), [t.name for t in mcp_tools])

    loop: LangGraphLoop = LangGraphLoop(
        system_prompt=settings.agent.system_prompt,
        llm_client=llm_client,
        builtin_tools=builtin,
        mcp_tools=mcp_tools or [],
        skill_loader=SkillLoader(),
    )
    loop.build()

    assert loop._graph is not None  # noqa: S101
    return loop._graph
