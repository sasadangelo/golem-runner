# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""LangGraph agent with dynamic tool loading from configuration."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from core.config import settings
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_ibm import ChatWatsonx
from langgraph.graph import (
    END,  # type: ignore[reportMissingTypeStubs]
    StateGraph,
)
from pydantic import SecretStr

if TYPE_CHECKING:
    from langgraph.graph.message import add_messages as add_messages  # type: ignore[reportMissingTypeStubs]
else:
    from langgraph.graph.message import add_messages as add_messages  # type: ignore[reportMissingTypeStubs]

from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from tools.http_tools import http_health_check
from tools.system_tools import execute_bash_command
from typing_extensions import TypedDict

logger = logging.getLogger("runner.agent")

# Central registry of available built-in skills
TOOL_REGISTRY: dict[str, BaseTool] = {
    "bash": execute_bash_command,
    "http_check": http_health_check,
}

# ---------------------------------------------------------------------------
# Boot-time file loading
# ---------------------------------------------------------------------------

_AGENTS_MD_PATH = Path("/app/AGENTS.md")
_SKILLS_DIR = Path("/app/skills")


def _load_agents_md() -> str | None:
    """Read AGENTS.md from /app/AGENTS.md if it exists.

    Returns:
        The file content as a string, or None if the file is absent.
    """
    if _AGENTS_MD_PATH.is_file():
        content = _AGENTS_MD_PATH.read_text(encoding="utf-8").strip()
        logger.info("AGENTS.md loaded from %s (%d chars)", _AGENTS_MD_PATH, len(content))
        return content
    return None


def _index_skills() -> dict[str, str]:
    """Scan /app/skills/*.md and return a mapping of skill-name → content.

    Returns:
        Dict mapping the stem of each .md filename to its content,
        e.g. ``{"read-logs": "# Read Logs skill …"}``.
        Empty dict when the directory does not exist or contains no .md files.
    """
    if not _SKILLS_DIR.is_dir():
        return {}
    index: dict[str, str] = {}
    for md_path in sorted(_SKILLS_DIR.glob("*.md")):
        skill_name = md_path.stem
        index[skill_name] = md_path.read_text(encoding="utf-8").strip()
        logger.info("Skill '%s' indexed from %s", skill_name, md_path)
    return index


# Loaded once at container startup — never mutated afterwards.
_agents_md: str | None = _load_agents_md()
_skill_index: dict[str, str] = _index_skills()


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _build_system_prompt(base_prompt: str, turn_messages: list[BaseMessage]) -> str:
    """Compose the full system prompt for a single LLM invocation.

    Layers (in order):
    1. The base system prompt from config.yaml.
    2. AGENTS.md behavioural context (if available).
    3. The most relevant skill instructions, injected lazily based on the last
       human message (if skills are indexed).

    Args:
        base_prompt:   The system_prompt from settings.
        turn_messages: The current conversation history (used for skill matching).

    Returns:
        A single string to use as the SystemMessage content.
    """
    parts: list[str] = [base_prompt]

    if _agents_md:
        parts.append(_agents_md)

    if _skill_index:
        # Find the last human message and match skill names against it.
        last_human = next(
            (m.content for m in reversed(turn_messages) if isinstance(m, HumanMessage)),
            "",
        )
        query = str(last_human).lower()
        for skill_name, skill_content in _skill_index.items():
            if skill_name.lower().replace("-", " ") in query or skill_name.lower() in query:
                parts.append(f"## Skill: {skill_name}\n\n{skill_content}")
                break  # inject at most one skill per turn

    return "\n\n".join(parts)


def build_agent(mcp_tools: list[BaseTool] | None = None) -> CompiledStateGraph:
    """Compile the LangGraph ReAct agent.

    Args:
        mcp_tools: Optional list of LangChain tools obtained from MCP servers at
                   boot time (loaded asynchronously in ``main.lifespan`` via
                   ``MultiServerMCPClient``).  Combined with the statically
                   configured built-in tools from ``TOOL_REGISTRY``.
    """
    base_prompt = settings.agent.system_prompt
    enabled_skills_env = settings.agent.enabled_skills  # e.g. "bash,http_check"

    selected_tools: list[BaseTool] = []
    if enabled_skills_env:
        for key in (s.strip() for s in enabled_skills_env.split(",") if s.strip()):
            if key in TOOL_REGISTRY:
                selected_tools.append(TOOL_REGISTRY[key])

    # Append MCP tools after the built-in ones so they are always available.
    if mcp_tools:
        selected_tools.extend(mcp_tools)
        logger.info("Registered %d MCP tool(s): %s", len(mcp_tools), [t.name for t in mcp_tools])

    llm = ChatWatsonx(
        model_id=settings.llm.model,
        url=SecretStr(settings.llm.url),
        project_id=settings.llm.project_id,
        api_key=settings.llm.api_key,
        params={"max_tokens": settings.llm.max_new_tokens},
    )

    if selected_tools:
        llm = llm.bind_tools(selected_tools)

    def call_model(state: AgentState) -> dict[str, list[BaseMessage]]:
        system_prompt = _build_system_prompt(base_prompt, list(state["messages"]))
        messages = [SystemMessage(content=system_prompt)] + list(state["messages"])
        response = llm.invoke(messages)
        return {"messages": [response]}

    builder = StateGraph(AgentState)
    builder.add_node("agent", call_model)

    if selected_tools:
        tool_node = ToolNode(selected_tools)
        builder.add_node("tools", tool_node)
        builder.set_entry_point("agent")

        def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
            last = state["messages"][-1]
            if isinstance(last, AIMessage) and last.tool_calls:
                return "tools"
            return "__end__"

        builder.add_conditional_edges("agent", should_continue)
        builder.add_edge("tools", "agent")
    else:
        builder.set_entry_point("agent")
        builder.add_edge("agent", END)

    return builder.compile()
