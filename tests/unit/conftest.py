# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Shared pytest fixtures for unit tests.

Mocks all heavy third-party modules (langchain_ibm, langchain_core LLM classes,
langgraph, langchain_mcp_adapters) before any source module is imported, so
tests run without credentials and without installing the full golem-runner
dependency tree.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _install_module_mocks() -> None:
    """Inject lightweight stubs into sys.modules for all runner dependencies."""
    stubs = [
        "langchain_ibm",
        "langgraph",
        "langgraph.graph",
        "langgraph.graph.message",
        "langgraph.graph.state",
        "langgraph.prebuilt",
        "langchain_mcp_adapters",
        "langchain_mcp_adapters.client",
        "dotenv",
    ]
    for name in stubs:
        if name not in sys.modules:
            sys.modules[name] = MagicMock()  # type: ignore[assignment]

    # dotenv.load_dotenv must be a no-op callable
    sys.modules["dotenv"].load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]

    # langgraph.graph must expose END and StateGraph
    lg_graph = sys.modules["langgraph.graph"]
    lg_graph.END = "END"  # type: ignore[attr-defined]
    lg_graph.StateGraph = MagicMock()  # type: ignore[attr-defined]

    # langgraph.graph.message must expose add_messages
    sys.modules["langgraph.graph.message"].add_messages = MagicMock()  # type: ignore[attr-defined]

    # langgraph.prebuilt must expose ToolNode
    sys.modules["langgraph.prebuilt"].ToolNode = MagicMock()  # type: ignore[attr-defined]

    # langchain_mcp_adapters.client must expose MultiServerMCPClient as an
    # async context manager that returns no tools
    mock_mcp_client = MagicMock()
    mock_mcp_client.__aenter__ = AsyncMock(return_value=mock_mcp_client)
    mock_mcp_client.__aexit__ = AsyncMock(return_value=False)
    mock_mcp_client.get_tools = AsyncMock(return_value=[])
    sys.modules["langchain_mcp_adapters.client"].MultiServerMCPClient = MagicMock(  # type: ignore[attr-defined]
        return_value=mock_mcp_client
    )


_install_module_mocks()


@pytest.fixture()
def client() -> TestClient:
    """FastAPI TestClient with agent_executor replaced by a no-op mock and
    TaskStore reset to empty state for each test.

    The lifespan is simplified by patching:
    - ``main._load_mcp_tools`` → returns [] (no real MCP connections)
    - ``agent.build_agent`` → returns a MagicMock compiled graph
    - ``main._register_with_control_plane`` → no-op (no real HTTP calls)
    """
    # Ensure a fresh import of main and agent for each fixture use
    for mod in ("agent", "main"):
        sys.modules.pop(mod, None)

    async def _noop_handshake(*_a: object, **_kw: object) -> None:
        pass

    async def _noop_load_mcp_tools(*_a: object, **_kw: object) -> list:
        return []

    with (
        patch("agent.build_agent", return_value=MagicMock()),
        patch("main._load_mcp_tools", side_effect=_noop_load_mcp_tools),
        patch("main._register_with_control_plane", side_effect=_noop_handshake),
    ):
        import main as m

        # Reset the shared TaskStore so tests are isolated from each other
        from golem_agent_sdk.router import task_store

        task_store.clear()

        return TestClient(m.app)
