# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""LangGraph agent with dynamic tool loading from configuration."""

from typing import TYPE_CHECKING, Annotated, Literal

from core.config import settings
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
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

# Central registry of available skills
TOOL_REGISTRY: dict[str, BaseTool] = {
    "bash": execute_bash_command,
    "http_check": http_health_check,
}


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def build_agent() -> CompiledStateGraph:
    system_prompt = settings.agent.system_prompt
    enabled_skills_env = settings.agent.enabled_skill  # e.g. "bash,http_check"

    selected_tools: list[BaseTool] = []
    if enabled_skills_env:
        for key in (s.strip() for s in enabled_skills_env.split(",") if s.strip()):
            if key in TOOL_REGISTRY:
                selected_tools.append(TOOL_REGISTRY[key])

    llm = ChatWatsonx(
        model_id=settings.llm.model,
        url=SecretStr(settings.llm.url),
        project_id=settings.llm.project_id,
        api_key=settings.llm.api_key,
    )

    if selected_tools:
        llm = llm.bind_tools(selected_tools)

    def call_model(state: AgentState) -> dict[str, list[BaseMessage]]:
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
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


# Compiled graph — instantiated once at container startup
agent_executor = build_agent()
