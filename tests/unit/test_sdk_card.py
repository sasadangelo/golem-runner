# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for golem_agent_sdk.card — AgentCard model and build_agent_card().

Covers:
  - build_agent_card() constructs a valid AgentCard from keyword arguments
  - AgentCard.to_dict() produces the correct A2A v1.0 wire shape
  - AgentCard.with_mcp_tools() adds MCP entries without mutating the original
  - Direct AgentCard construction
  - All required A2A v1.0 fields are present in the serialised dict
"""


from golem_agent_sdk.card import AgentCard, build_agent_card

# ---------------------------------------------------------------------------
# build_agent_card — factory
# ---------------------------------------------------------------------------


class TestBuildAgentCard:
    """build_agent_card() constructs AgentCard correctly from keyword args."""

    def test_required_fields_set(self) -> None:
        """All required fields are populated from the arguments."""
        card = build_agent_card(
            agent_id="agent-001",
            name="Test Agent",
            description="Does things",
            endpoint="http://localhost:8001",
        )
        assert card.id == "agent-001"
        assert card.name == "Test Agent"
        assert card.description == "Does things"
        assert card.endpoint == "http://localhost:8001"

    def test_default_version(self) -> None:
        """Version defaults to '0.1.0' when not supplied."""
        card = build_agent_card(
            agent_id="a", name="N", description="D", endpoint="http://e"
        )
        assert card.version == "0.1.0"

    def test_custom_version(self) -> None:
        """Custom version is stored correctly."""
        card = build_agent_card(
            agent_id="a", name="N", description="D", endpoint="http://e", version="1.2.3"
        )
        assert card.version == "1.2.3"

    def test_builtin_tools_populated(self) -> None:
        """Builtin tools appear in card.tools.builtin."""
        card = build_agent_card(
            agent_id="a", name="N", description="D", endpoint="http://e",
            builtin_tools=["bash", "http_check"],
        )
        names = [t.name for t in card.tools.builtin]
        assert "bash" in names
        assert "http_check" in names

    def test_mcp_tools_empty_by_default(self) -> None:
        """MCP tools list is empty when not yet populated."""
        card = build_agent_card(agent_id="a", name="N", description="D", endpoint="http://e")
        assert card.tools.mcp == []

    def test_skills_empty_by_default(self) -> None:
        """Skills list is empty when not provided."""
        card = build_agent_card(agent_id="a", name="N", description="D", endpoint="http://e")
        assert card.skills == []

    def test_skills_populated(self) -> None:
        """Provided skills are stored on the card."""
        card = build_agent_card(
            agent_id="a", name="N", description="D", endpoint="http://e",
            skills=["analyse-logs", "write-report"],
        )
        assert "analyse-logs" in card.skills
        assert "write-report" in card.skills

    def test_capabilities_defaults(self) -> None:
        """Default capabilities: streaming=True, push_notifications=False."""
        card = build_agent_card(agent_id="a", name="N", description="D", endpoint="http://e")
        assert card.capabilities.streaming is True
        assert card.capabilities.push_notifications is False

    def test_capabilities_override(self) -> None:
        """Custom capability flags are honoured."""
        card = build_agent_card(
            agent_id="a", name="N", description="D", endpoint="http://e",
            streaming=False,
            push_notifications=True,
        )
        assert card.capabilities.streaming is False
        assert card.capabilities.push_notifications is True


# ---------------------------------------------------------------------------
# AgentCard.to_dict() — wire serialisation
# ---------------------------------------------------------------------------


class TestAgentCardToDict:
    """to_dict() produces a JSON-serialisable dict matching the A2A v1.0 shape."""

    def _card(self) -> AgentCard:
        return build_agent_card(
            agent_id="agent-42",
            name="Golem",
            description="An agent",
            endpoint="http://agent:8001",
            builtin_tools=["bash"],
        )

    def test_required_a2a_fields_present(self) -> None:
        """All mandatory A2A v1.0 fields must appear in the serialised dict."""
        d = self._card().to_dict()
        for field in ("id", "name", "description", "version", "endpoint", "capabilities", "skills", "tools"):
            assert field in d, f"Missing field: {field}"

    def test_id_matches(self) -> None:
        assert self._card().to_dict()["id"] == "agent-42"

    def test_capabilities_uses_camel_case_alias(self) -> None:
        """pushNotifications (camelCase) must appear in the wire dict."""
        caps = self._card().to_dict()["capabilities"]
        assert "pushNotifications" in caps
        assert "streaming" in caps

    def test_tools_shape(self) -> None:
        """tools.builtin entries must have 'id' and 'name' keys."""
        tools = self._card().to_dict()["tools"]
        assert "builtin" in tools
        assert "mcp" in tools
        assert tools["builtin"][0]["id"] == "bash"
        assert tools["builtin"][0]["name"] == "bash"

    def test_skills_is_list(self) -> None:
        assert isinstance(self._card().to_dict()["skills"], list)


# ---------------------------------------------------------------------------
# AgentCard.with_mcp_tools() — immutable update
# ---------------------------------------------------------------------------


class TestWithMcpTools:
    """with_mcp_tools() returns a new card; the original is unchanged."""

    def test_mcp_tools_added(self) -> None:
        original = build_agent_card(agent_id="a", name="N", description="D", endpoint="http://e")
        updated = original.with_mcp_tools(["search", "browse"])
        names = [t.name for t in updated.tools.mcp]
        assert "search" in names
        assert "browse" in names

    def test_original_unchanged(self) -> None:
        original = build_agent_card(agent_id="a", name="N", description="D", endpoint="http://e")
        original.with_mcp_tools(["search"])
        assert original.tools.mcp == []

    def test_builtin_tools_preserved(self) -> None:
        """Builtin tools must not be wiped when mcp tools are added."""
        original = build_agent_card(
            agent_id="a", name="N", description="D", endpoint="http://e",
            builtin_tools=["bash"],
        )
        updated = original.with_mcp_tools(["search"])
        assert any(t.name == "bash" for t in updated.tools.builtin)

    def test_empty_mcp_list(self) -> None:
        """Passing an empty list clears the mcp section (or keeps it empty)."""
        original = build_agent_card(agent_id="a", name="N", description="D", endpoint="http://e")
        updated = original.with_mcp_tools([])
        assert updated.tools.mcp == []

    def test_to_dict_after_mcp_update(self) -> None:
        """to_dict() on the updated card reflects the new MCP tool names."""
        card = build_agent_card(
            agent_id="a", name="N", description="D", endpoint="http://e"
        ).with_mcp_tools(["wiki"])
        mcp_names = [e["name"] for e in card.to_dict()["tools"]["mcp"]]
        assert "wiki" in mcp_names
