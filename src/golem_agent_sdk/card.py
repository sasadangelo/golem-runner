# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""A2A Agent Card model and builder for golem-agent-sdk.

The Agent Card is served at ``/.well-known/agent.json`` by every runner and is
also pushed to the Control Plane during the startup handshake.  It is defined
here — with no LLM dependency — so non-LLM agents can build and serve it
without pulling in the full runner stack.

Typical usage
-------------
    from golem_agent_sdk.card import AgentCard, AgentCapabilities, AgentTools, build_agent_card

    card = build_agent_card(
        agent_id="my-agent-001",
        name="My Agent",
        description="Does useful things",
        endpoint="http://my-agent:8001",
        builtin_tools=["http_check"],
    )
    # Later, after MCP tools are resolved at boot:
    card = card.with_mcp_tools(["search", "browse"])
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentCapabilities(BaseModel):
    """Capability flags advertised in the Agent Card."""

    streaming: bool = True
    push_notifications: bool = Field(default=False, alias="pushNotifications")

    model_config = {"populate_by_name": True}


class ToolEntry(BaseModel):
    """A single tool entry inside the tools section of the Agent Card."""

    id: str
    name: str


class AgentTools(BaseModel):
    """Built-in and MCP tools section of the Agent Card."""

    builtin: list[ToolEntry] = Field(default_factory=list)
    mcp: list[ToolEntry] = Field(default_factory=list)


class AgentCard(BaseModel):
    """A2A v1.0 Agent Card — the self-description document for an agent.

    Served at ``/.well-known/agent.json`` and pushed to the Control Plane
    during the startup handshake.

    All fields are plain Python values (strings, lists) so the card can be
    JSON-serialised with ``model.model_dump(by_alias=True)`` and transmitted
    without any LLM or framework dependency.
    """

    id: str = Field(description="Unique identifier for this agent instance.")
    name: str = Field(description="Human-readable agent name.")
    description: str = Field(description="Short description shown in peer agent UIs and the Control Plane.")
    version: str = Field(default="0.1.0", description="Agent software version string.")
    endpoint: str = Field(description="Public base URL where this agent listens (e.g. http://agent:8001).")
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    skills: list[str] = Field(default_factory=list, description="Skill names exposed by this agent.")
    tools: AgentTools = Field(default_factory=AgentTools)

    def with_mcp_tools(self, tool_names: list[str]) -> AgentCard:
        """Return a new AgentCard with the mcp tools section populated.

        Intended to be called after MCP server connections are resolved at
        boot time, when the available tool names are finally known.

        Args:
            tool_names: Names of the MCP tools now available to this agent.

        Returns:
            A new AgentCard instance with the mcp tools section replaced.
        """
        updated_tools = self.tools.model_copy(
            update={"mcp": [ToolEntry(id=name, name=name) for name in tool_names]}
        )
        return self.model_copy(update={"tools": updated_tools})

    def to_dict(self) -> dict:
        """Serialise the card to a plain dict suitable for JSON responses.

        Uses camelCase aliases (``pushNotifications``) so the output matches
        the A2A v1.0 wire format.

        Returns:
            A JSON-serialisable dict representing the Agent Card.
        """
        return self.model_dump(by_alias=True)


def build_agent_card(
    *,
    agent_id: str,
    name: str,
    description: str,
    endpoint: str,
    version: str = "0.1.0",
    builtin_tools: list[str] | None = None,
    skills: list[str] | None = None,
    streaming: bool = True,
    push_notifications: bool = False,
) -> AgentCard:
    """Build an AgentCard from individual configuration values.

    This is the preferred factory for constructing a card at runner startup.
    MCP tools should be added afterwards via ``card.with_mcp_tools()``, once
    the MCP connections are established.

    Args:
        agent_id:          Unique identifier for this agent instance.
        name:              Human-readable agent name.
        description:       Short description of this agent.
        endpoint:          Public base URL of this agent (e.g. http://agent:8001).
        version:           Software version string (default: "0.1.0").
        builtin_tools:     Names of built-in tools enabled for this agent.
        skills:            Skill names exposed by this agent.
        streaming:         Whether this agent supports streaming responses.
        push_notifications: Whether this agent supports A2A push notifications.

    Returns:
        A fully populated AgentCard ready to be served or transmitted.
    """
    tools = AgentTools(
        builtin=[ToolEntry(id=t, name=t) for t in (builtin_tools or [])],
        mcp=[],
    )
    return AgentCard(
        id=agent_id,
        name=name,
        description=description,
        version=version,
        endpoint=endpoint,
        capabilities=AgentCapabilities(streaming=streaming, pushNotifications=push_notifications),
        skills=skills or [],
        tools=tools,
    )
