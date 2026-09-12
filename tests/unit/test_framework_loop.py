# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for golem_framework — AgentLoop ABC and LangGraphLoop.

All LangGraph and LangChain dependencies are mocked by conftest so no
credentials or running services are required.

Covers:
  - AgentLoop is abstract — cannot be instantiated directly
  - LangGraphLoop.build() loads persona + skills from SkillLoader
  - LangGraphLoop.invoke() delegates to the compiled graph
  - LangGraphLoop.astream_events() yields events from the graph
  - SkillLoader.load_persona() returns None when file is absent
  - SkillLoader.load_skills() returns empty dict when dir is absent
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

# conftest has already installed stubs for langgraph / langchain_ibm / etc.


# ---------------------------------------------------------------------------
# AgentLoop ABC
# ---------------------------------------------------------------------------


def test_agent_loop_is_abstract() -> None:
    """AgentLoop cannot be instantiated — it is an ABC."""
    from golem_framework.loop.base import AgentLoop

    with pytest.raises(TypeError):
        AgentLoop()  # type: ignore[abstract]


def test_agent_loop_subclass_must_implement_all_methods() -> None:
    """A subclass that omits any abstract method cannot be instantiated."""
    from golem_framework.loop.base import AgentLoop

    class Incomplete(AgentLoop):
        def build(self) -> None:
            pass

        # missing invoke and astream_events

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# SkillLoader
# ---------------------------------------------------------------------------


class TestSkillLoader:
    """SkillLoader reads persona and skills from the filesystem."""

    def test_load_persona_returns_none_when_file_absent(self, tmp_path: Path) -> None:
        from golem_framework.skill_loader import SkillLoader

        loader = SkillLoader(agents_md_path=tmp_path / "AGENTS.md", skills_dir=tmp_path / "skills")
        assert loader.load_persona() is None

    def test_load_persona_returns_content(self, tmp_path: Path) -> None:
        from golem_framework.skill_loader import SkillLoader

        md = tmp_path / "AGENTS.md"
        md.write_text("You are helpful.\n")
        loader = SkillLoader(agents_md_path=md, skills_dir=tmp_path / "skills")
        assert loader.load_persona() == "You are helpful."

    def test_load_skills_returns_empty_when_dir_absent(self, tmp_path: Path) -> None:
        from golem_framework.skill_loader import SkillLoader

        loader = SkillLoader(agents_md_path=tmp_path / "AGENTS.md", skills_dir=tmp_path / "skills")
        assert loader.load_skills() == {}

    def test_load_skills_indexes_all_md_files(self, tmp_path: Path) -> None:
        from golem_framework.skill_loader import SkillLoader

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "read-logs.md").write_text("# Read Logs")
        (skills_dir / "summarize.md").write_text("# Summarize")
        loader = SkillLoader(agents_md_path=tmp_path / "AGENTS.md", skills_dir=skills_dir)
        index = loader.load_skills()
        assert set(index.keys()) == {"read-logs", "summarize"}
        assert index["read-logs"] == "# Read Logs"

    def test_load_skills_ignores_non_md_files(self, tmp_path: Path) -> None:
        from golem_framework.skill_loader import SkillLoader

        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "skill.md").write_text("content")
        (skills_dir / "notes.txt").write_text("ignored")
        loader = SkillLoader(agents_md_path=tmp_path / "AGENTS.md", skills_dir=skills_dir)
        assert list(loader.load_skills().keys()) == ["skill"]


# ---------------------------------------------------------------------------
# LangGraphLoop — build + invoke
# ---------------------------------------------------------------------------


def _make_loop(tmp_path: Path, tools: list | None = None) -> Any:
    """Construct a LangGraphLoop with a mocked LLMClient."""
    from unittest.mock import MagicMock

    from golem_framework.llm_gateway.base import LLMClient
    from golem_framework.loop.langgraph import LangGraphLoop
    from golem_framework.skill_loader import SkillLoader

    # Minimal LLMClient stub — as_chat_model() returns the mocked ChatModel
    class _FakeClient(LLMClient):
        def as_chat_model(self):  # noqa: ANN201
            return MagicMock()

    return LangGraphLoop(
        system_prompt="You are helpful.",
        llm_client=_FakeClient(),
        builtin_tools=tools or [],
        skill_loader=SkillLoader(
            agents_md_path=tmp_path / "AGENTS.md",
            skills_dir=tmp_path / "skills",
        ),
    )


class TestLangGraphLoopBuild:
    """LangGraphLoop.build() compiles the graph."""

    def test_build_sets_graph(self, tmp_path: Path) -> None:
        """After build(), _graph must not be None."""
        loop = _make_loop(tmp_path)
        loop.build()
        assert loop._graph is not None

    def test_build_loads_persona(self, tmp_path: Path) -> None:
        """build() stores the persona when AGENTS.md is present."""
        (tmp_path / "AGENTS.md").write_text("I am a bot.")
        loop = _make_loop(tmp_path)
        loop.build()
        assert loop._persona == "I am a bot."

    def test_build_loads_skills(self, tmp_path: Path) -> None:
        """build() populates _skill_index when skills dir contains .md files."""
        skills = tmp_path / "skills"
        skills.mkdir()
        (skills / "my-skill.md").write_text("skill content")
        loop = _make_loop(tmp_path)
        loop.build()
        assert "my-skill" in loop._skill_index


class TestLangGraphLoopInvoke:
    """LangGraphLoop.invoke() calls the compiled graph."""

    def test_invoke_returns_last_message_content(self, tmp_path: Path) -> None:
        """invoke() must return the content of the last message in the result."""
        from langchain_core.messages import AIMessage

        loop = _make_loop(tmp_path)
        loop.build()

        mock_result = {"messages": [AIMessage(content="The answer is 42.")]}
        loop._graph.invoke = MagicMock(return_value=mock_result)  # type: ignore[union-attr]

        result = loop.invoke([{"role": "human", "content": "What is 6*7?"}])
        assert result == "The answer is 42."

    def test_invoke_raises_before_build(self, tmp_path: Path) -> None:
        """invoke() must raise AssertionError if build() was not called first."""
        loop = _make_loop(tmp_path)
        with pytest.raises(AssertionError):
            loop.invoke([{"role": "human", "content": "hello"}])


class TestLangGraphLoopToLcMessages:
    """_to_lc_messages converts role/content dicts to LangChain message objects."""

    def test_human_role(self) -> None:
        from langchain_core.messages import HumanMessage

        from golem_framework.loop.langgraph import LangGraphLoop

        result = LangGraphLoop._to_lc_messages([{"role": "human", "content": "hi"}])
        assert isinstance(result[0], HumanMessage)
        assert result[0].content == "hi"

    def test_ai_role(self) -> None:
        from langchain_core.messages import AIMessage

        from golem_framework.loop.langgraph import LangGraphLoop

        result = LangGraphLoop._to_lc_messages([{"role": "ai", "content": "hello"}])
        assert isinstance(result[0], AIMessage)

    def test_unknown_role_defaults_to_human(self) -> None:
        from langchain_core.messages import HumanMessage

        from golem_framework.loop.langgraph import LangGraphLoop

        result = LangGraphLoop._to_lc_messages([{"role": "xyz", "content": "msg"}])
        assert isinstance(result[0], HumanMessage)

    def test_user_alias(self) -> None:
        from langchain_core.messages import HumanMessage

        from golem_framework.loop.langgraph import LangGraphLoop

        result = LangGraphLoop._to_lc_messages([{"role": "user", "content": "msg"}])
        assert isinstance(result[0], HumanMessage)


# ---------------------------------------------------------------------------
# LangGraphLoop — astream_events
# ---------------------------------------------------------------------------


class TestLangGraphLoopAstreamEvents:
    """LangGraphLoop.astream_events() yields events from the graph."""

    @pytest.mark.asyncio
    async def test_astream_events_yields_from_graph(self, tmp_path: Path) -> None:
        """astream_events must forward every event from the underlying graph."""
        loop = _make_loop(tmp_path)
        loop.build()

        fake_events = [
            {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content="Hello")}},
            {"event": "on_chat_model_stream", "data": {"chunk": MagicMock(content=" world")}},
        ]

        async def _fake_stream(*_a: Any, **_kw: Any):
            for ev in fake_events:
                yield ev

        loop._graph.astream_events = _fake_stream  # type: ignore[union-attr]

        collected = []
        async for event in loop.astream_events([{"role": "human", "content": "hi"}]):
            collected.append(event)

        assert len(collected) == 2
        assert collected[0]["event"] == "on_chat_model_stream"

    @pytest.mark.asyncio
    async def test_astream_events_raises_before_build(self, tmp_path: Path) -> None:
        """astream_events must raise AssertionError if build() was not called."""
        loop = _make_loop(tmp_path)
        with pytest.raises(AssertionError):
            async for _ in loop.astream_events([{"role": "human", "content": "hi"}]):
                pass
