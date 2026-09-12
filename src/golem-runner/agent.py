# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""LangGraph agent with dynamic tool loading from configuration.

Two categories of tools are available to the agent:

Built-in tools  (configure via ``agent.builtin_tools`` in config.yaml)
----------------------------------------------------------------------
- ``bash``        execute_bash_command  — run shell commands inside the pod
- ``http_check``  http_health_check     — probe an HTTP endpoint
- ``delegate``    delegate_to_agent     — send a sub-task to another agent via CP

MCP tools  (configure via ``agent.mcp_servers`` in config.yaml)
---------------------------------------------------------------
Loaded at boot from each MCP server listed in ``agent.mcp_servers`` and
registered into the LangGraph tool node alongside the built-in tools.
"""

import logging
from pathlib import Path
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_ibm import ChatWatsonx
from langgraph.graph import (
    END,  # type: ignore[reportMissingTypeStubs]
    StateGraph,
)
from langgraph.graph.message import add_messages  # type: ignore[reportMissingTypeStubs]
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from pydantic import SecretStr
from typing_extensions import TypedDict

from core.config import settings
from tools.a2a_tools import delegate_to_agent
from tools.http_tools import http_health_check
from tools.system_tools import execute_bash_command

logger = logging.getLogger("runner.agent")

# Central registry of available built-in tools.
# Add the tool name to ``builtin_tools`` in config.yaml to activate it.
TOOL_REGISTRY: dict[str, BaseTool] = {
    "bash": execute_bash_command,
    "http_check": http_health_check,
    "delegate": delegate_to_agent,
}

# ---------------------------------------------------------------------------
# Boot-time file loading
# ---------------------------------------------------------------------------

_AGENTS_MD_PATH: Path = Path("/app/AGENTS.md")
_SKILLS_DIR: Path = Path("/app/skills")


def _load_agents_md() -> str | None:
    """Read AGENTS.md from /app/AGENTS.md if it exists.

    Returns:
        The file content as a string, or None if the file is absent.
    """
    if _AGENTS_MD_PATH.is_file():
        content: str = _AGENTS_MD_PATH.read_text(encoding="utf-8").strip()
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
    for md_path in sorted(_SKILLS_DIR.glob(pattern="*.md")):
        skill_name: str = md_path.stem
        index[skill_name] = md_path.read_text(encoding="utf-8").strip()
        logger.info("Skill '%s' indexed from %s", skill_name, md_path)
    return index


# Loaded once at container startup — never mutated afterwards.
_agents_md: str | None = _load_agents_md()
_skill_index: dict[str, str] = _index_skills()


class AgentState(TypedDict):
    """State carried across nodes of one LangGraph agent execution.

    ``add_messages`` merges each node's returned messages into the existing
    conversation instead of replacing the ``messages`` list.
    """

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
        query: str = str(last_human).lower()
        for skill_name, skill_content in _skill_index.items():
            if skill_name.lower().replace("-", " ") in query or skill_name.lower() in query:
                parts.append(f"## Skill: {skill_name}\n\n{skill_content}")
                break  # inject at most one skill per turn

    return "\n\n".join(parts)


def build_agent(mcp_tools: list[BaseTool] | None = None) -> CompiledStateGraph:
    """Build and compile the LangGraph agent graph used by every chat turn.

    The graph owns the control flow, while ``AgentState.messages`` owns the
    conversation data passed between nodes. Each node returns only newly
    created messages; ``add_messages`` appends them to the existing state.

    Two graph structures are built depending on whether any tools are active:

    With tools (built-in and/or MCP tools available)::

        START
          |
          v
        agent (build prompt and invoke Watsonx)
          |
          v
        last AI message has tool_calls?
          | yes                       | no
          v                           v
        tools (execute ToolNode)      END
          |
          +----------> agent

        The loop repeats until the model emits an AIMessage without tool
        calls. The runner's recursion limit bounds the number of hops.

    Without tools (no built-in tools enabled and no MCP tools loaded)::

        START
          |
          v
        agent (build prompt and invoke Watsonx)
          |
          v
        END

        A single model invocation produces the final answer directly.

    Args:
        mcp_tools: Optional list of LangChain tools obtained from MCP servers at
            boot time by ``main._load_mcp_tools``. Combined with built-in tools
            selected through ``agent.builtin_tools``.

    Returns:
        A compiled graph accepting and returning an ``AgentState``.
    """
    base_prompt: str = settings.agent.system_prompt

    # Select only built-in tools explicitly enabled in configuration.
    selected_tools: list[BaseTool] = []
    for key in settings.agent.builtin_tools:
        if key in TOOL_REGISTRY:
            selected_tools.append(TOOL_REGISTRY[key])

    # MCP tools are already loaded at startup and are always added when available.
    if mcp_tools:
        selected_tools.extend(mcp_tools)
        logger.info("Registered %d MCP tool(s): %s", len(mcp_tools), [t.name for t in mcp_tools])

    # Instantiate the Watsonx chat model from the LLM configuration.
    llm = ChatWatsonx(
        model_id=settings.llm.model,
        url=SecretStr(settings.llm.url),
        project_id=settings.llm.project_id,
        api_key=settings.llm.api_key,
        params={"max_tokens": settings.llm.max_new_tokens},
    )

    # Binding tool schemas lets the model return structured tool-call requests.
    if selected_tools:
        llm = llm.bind_tools(tools=selected_tools)

    def call_model(state: AgentState) -> dict[str, list[BaseMessage]]:
        """Invoke Watsonx and return its response as an incremental state update."""
        # The prompt is rebuilt on every model pass: after a tool result returns
        # to this node, the model sees that result in ``state["messages"]``.
        system_prompt = _build_system_prompt(base_prompt, list(state["messages"]))
        messages: list[BaseMessage] = [SystemMessage(content=system_prompt)] + list(state["messages"])
        response: AIMessage = llm.invoke(messages)
        # ``add_messages`` appends this response to AgentState.messages.
        return {"messages": [response]}

    # Define the state machine. Nodes receive AgentState and return state updates.
    builder: StateGraph[AgentState, None, AgentState, AgentState] = StateGraph(state_schema=AgentState)
    builder.add_node("agent", call_model)

    if selected_tools:
        # The ToolNode executes tool calls found in the latest AIMessage.
        tool_node: ToolNode = ToolNode(tools=selected_tools)
        builder.add_node("tools", tool_node)
        builder.set_entry_point(key="agent")

        def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
            """Route tool-call responses to tools; treat all others as final answers."""
            last: BaseMessage = state["messages"][-1]
            if isinstance(last, AIMessage) and last.tool_calls:
                return "tools"
            return "__end__"

        # agent → tools → agent continues until the model emits no tool calls.
        builder.add_conditional_edges("agent", should_continue)
        builder.add_edge("tools", "agent")
    else:
        # Without tools, a single model invocation is the whole graph.
        builder.set_entry_point("agent")
        builder.add_edge("agent", END)

    # Validate and turn the declarative StateGraph into its runnable executor.
    return builder.compile()
