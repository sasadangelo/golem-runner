# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""LangGraphLoop — concrete AgentLoop backed by LangGraph + WatsonX (MVP).

Implements the ``AgentLoop`` ABC using a ReAct-style LangGraph state machine.
The LLM is currently always WatsonX; swapping the provider is tracked in the
roadmap as the LLM Gateway work (MVP 2).

Graph topology
--------------
With tools::

    START → agent → (tool_calls?) → tools → agent → … → END

Without tools::

    START → agent → END

The loop exits when the model produces an AIMessage with no tool calls, or
when the recursion limit is hit.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_ibm import ChatWatsonx
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode
from pydantic import SecretStr
from typing_extensions import TypedDict

from golem_framework.loop.base import AgentLoop
from golem_framework.skill_loader import SkillLoader

logger = logging.getLogger("runner.loop")


class _AgentState(TypedDict):
    """Internal LangGraph state — carries the full conversation across nodes."""

    messages: Annotated[list[BaseMessage], add_messages]


class LangGraphLoop(AgentLoop):
    """ReAct agentic loop built on LangGraph + WatsonX.

    Args:
        system_prompt:  Base system prompt from ``config.yaml``.
        llm_model:      WatsonX model ID.
        llm_url:        WatsonX service URL.
        llm_project_id: WatsonX project ID.
        llm_api_key:    WatsonX API key (resolved from env at construction time).
        max_new_tokens: Maximum tokens the model may generate per invocation.
        builtin_tools:  Pre-resolved list of built-in BaseTool instances.
        mcp_tools:      MCP tool instances loaded at boot from MCP servers.
        skill_loader:   SkillLoader instance for persona + skill injection.
        recursion_limit: Maximum number of tool-call hops before aborting.
    """

    def __init__(
        self,
        *,
        system_prompt: str,
        llm_model: str,
        llm_url: str,
        llm_project_id: str,
        llm_api_key: str | None,
        max_new_tokens: int = 2048,
        builtin_tools: list[BaseTool] | None = None,
        mcp_tools: list[BaseTool] | None = None,
        skill_loader: SkillLoader | None = None,
        recursion_limit: int = 50,
    ) -> None:
        self._system_prompt = system_prompt
        self._llm_model = llm_model
        self._llm_url = llm_url
        self._llm_project_id = llm_project_id
        self._llm_api_key = llm_api_key
        self._max_new_tokens = max_new_tokens
        self._tools: list[BaseTool] = list(builtin_tools or []) + list(mcp_tools or [])
        self._skill_loader = skill_loader or SkillLoader()
        self._recursion_limit = recursion_limit

        # Loaded at build() time
        self._persona: str | None = None
        self._skill_index: dict[str, str] = {}
        self._graph: CompiledStateGraph | None = None

    # ------------------------------------------------------------------
    # AgentLoop interface
    # ------------------------------------------------------------------

    def build(self) -> None:
        """Compile the LangGraph state machine.

        Loads persona + skills from disk, wires tools into the graph, and
        compiles the StateGraph into its runnable form.
        """
        self._persona = self._skill_loader.load_persona()
        self._skill_index = self._skill_loader.load_skills()

        llm = ChatWatsonx(
            model_id=self._llm_model,
            url=SecretStr(self._llm_url),
            project_id=self._llm_project_id,
            api_key=self._llm_api_key,
            params={"max_tokens": self._max_new_tokens},
        )

        if self._tools:
            llm = llm.bind_tools(tools=self._tools)
            logger.info(
                "LangGraphLoop compiled — %d tool(s): %s",
                len(self._tools),
                [t.name for t in self._tools],
            )
        else:
            logger.info("LangGraphLoop compiled — no tools")

        def call_model(state: _AgentState) -> dict[str, list[BaseMessage]]:
            system_prompt = self._build_system_prompt(list(state["messages"]))
            msgs: list[BaseMessage] = [SystemMessage(content=system_prompt)] + list(state["messages"])
            response: AIMessage = llm.invoke(msgs)
            return {"messages": [response]}

        builder: StateGraph = StateGraph(state_schema=_AgentState)
        builder.add_node("agent", call_model)

        if self._tools:
            tool_node = ToolNode(tools=self._tools)
            builder.add_node("tools", tool_node)
            builder.set_entry_point("agent")

            def should_continue(state: _AgentState) -> Literal["tools", "__end__"]:
                last: BaseMessage = state["messages"][-1]
                if isinstance(last, AIMessage) and last.tool_calls:
                    return "tools"
                return "__end__"

            builder.add_conditional_edges("agent", should_continue)
            builder.add_edge("tools", "agent")
        else:
            builder.set_entry_point("agent")
            builder.add_edge("agent", END)

        self._graph = builder.compile()

    def invoke(self, messages: list[dict[str, Any]]) -> str:
        """Run a single turn synchronously.

        Args:
            messages: Conversation turns as dicts with ``role`` and ``content``.

        Returns:
            The agent's final plain-text reply.
        """
        assert self._graph is not None, "LangGraphLoop.build() must be called first"  # noqa: S101
        lc_messages = self._to_lc_messages(messages)
        result = self._graph.invoke(
            {"messages": lc_messages},
            config={"recursion_limit": self._recursion_limit},
        )
        return str(result["messages"][-1].content)

    async def astream_events(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream LangChain v2 events for a single turn.

        Args:
            messages: Conversation turns as dicts with ``role`` and ``content``.
            **kwargs: Forwarded to ``astream_events`` (e.g. ``config``).

        Yields:
            LangChain-style event dicts.
        """
        assert self._graph is not None, "LangGraphLoop.build() must be called first"  # noqa: S101
        lc_messages = self._to_lc_messages(messages)
        config = kwargs.pop("config", {"recursion_limit": self._recursion_limit})
        async for event in self._graph.astream_events(
            {"messages": lc_messages},
            version="v2",
            config=config,
            **kwargs,
        ):
            yield event

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self, turn_messages: list[BaseMessage]) -> str:
        """Compose the system prompt for one LLM invocation.

        Layers (in order):
          1. Base system prompt from config.yaml.
          2. Persona (AGENTS.md) if loaded.
          3. The most relevant skill, matched lazily against the last human message.

        Args:
            turn_messages: Current conversation history.

        Returns:
            Single string to use as the SystemMessage content.
        """
        parts: list[str] = [self._system_prompt]

        if self._persona:
            parts.append(self._persona)

        if self._skill_index:
            last_human = next(
                (m.content for m in reversed(turn_messages) if isinstance(m, HumanMessage)),
                "",
            )
            query = str(last_human).lower()
            for skill_name, skill_content in self._skill_index.items():
                if skill_name.lower().replace("-", " ") in query or skill_name.lower() in query:
                    parts.append(f"## Skill: {skill_name}\n\n{skill_content}")
                    break

        return "\n\n".join(parts)

    @staticmethod
    def _to_lc_messages(messages: list[dict[str, Any]]) -> list[BaseMessage]:
        """Convert role/content dicts to LangChain message objects.

        Accepts dicts with ``role`` in ``human|user``, ``ai|assistant``,
        or ``system``.  Unknown roles default to HumanMessage.

        Args:
            messages: List of message dicts.

        Returns:
            List of LangChain BaseMessage instances.
        """
        lc: list[BaseMessage] = []
        for m in messages:
            role = m.get("role", "human")
            content = m.get("content", "")
            if role in ("human", "user"):
                lc.append(HumanMessage(content=content))
            elif role in ("ai", "assistant"):
                lc.append(AIMessage(content=content))
            elif role == "system":
                lc.append(SystemMessage(content=content))
            else:
                lc.append(HumanMessage(content=content))
        return lc
