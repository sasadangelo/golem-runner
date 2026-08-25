# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for core.config — AgentConfig, MCPServerConfig, EnvSecretRef."""

import sys

import pytest

# Ensure mocks are installed before importing source modules
# (conftest._install_module_mocks runs at collection time, so we're safe here).


def _fresh_config():
    """Re-import core.config with a clean module cache."""
    sys.modules.pop("core.config", None)
    import core.config as cfg

    return cfg


class TestMCPServerConfigCoercion:
    """AgentConfig._coerce_mcp_servers converts bare URI strings to MCPServerConfig."""

    def test_bare_string_is_coerced(self) -> None:
        cfg = _fresh_config()
        agent = cfg.AgentConfig(mcp_servers=["http://localhost:8000/mcp"])  # type: ignore[call-arg]
        assert len(agent.mcp_servers) == 1
        assert agent.mcp_servers[0].url == "http://localhost:8000/mcp"
        assert agent.mcp_servers[0].headers == {}

    def test_object_form_preserved(self) -> None:
        cfg = _fresh_config()
        agent = cfg.AgentConfig(  # type: ignore[call-arg]
            mcp_servers=[{"url": "http://localhost:8000/mcp", "headers": {"X-Foo": "bar"}}]
        )
        assert agent.mcp_servers[0].headers == {"X-Foo": "bar"}

    def test_empty_list(self) -> None:
        cfg = _fresh_config()
        agent = cfg.AgentConfig(mcp_servers=[])  # type: ignore[call-arg]
        assert agent.mcp_servers == []


class TestMCPServerConfigResolvedHeaders:
    """MCPServerConfig.resolved_headers() substitutes $VAR placeholders from env."""

    def test_plain_value_unchanged(self) -> None:
        cfg = _fresh_config()
        srv = cfg.MCPServerConfig(url="http://x", headers={"X-Key": "plain-value"})
        assert srv.resolved_headers() == {"X-Key": "plain-value"}

    def test_dollar_var_resolved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_TOKEN", "secret123")
        cfg = _fresh_config()
        # $VAR appears mid-value (e.g. "Bearer $MY_TOKEN")
        srv = cfg.MCPServerConfig(url="http://x", headers={"Authorization": "Bearer $MY_TOKEN"})
        assert srv.resolved_headers() == {"Authorization": "Bearer secret123"}

    def test_missing_env_var_returns_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MISSING_VAR", raising=False)
        cfg = _fresh_config()
        srv = cfg.MCPServerConfig(url="http://x", headers={"Authorization": "Bearer $MISSING_VAR"})
        result = srv.resolved_headers()
        # Missing var is replaced with empty string → "Bearer "
        assert result["Authorization"] == "Bearer "

    def test_no_headers_returns_empty_dict(self) -> None:
        cfg = _fresh_config()
        srv = cfg.MCPServerConfig(url="http://x")
        assert srv.resolved_headers() == {}


class TestEnvSecrets:
    """AgentConfig.env_secrets is a list of secret name strings."""

    def test_empty_by_default(self) -> None:
        cfg = _fresh_config()
        agent = cfg.AgentConfig()  # type: ignore[call-arg]
        assert agent.env_secrets == []

    def test_single_secret(self) -> None:
        cfg = _fresh_config()
        agent = cfg.AgentConfig(env_secrets=["github-mcp-credentials"])  # type: ignore[call-arg]
        assert agent.env_secrets == ["github-mcp-credentials"]

    def test_multiple_secrets(self) -> None:
        cfg = _fresh_config()
        agent = cfg.AgentConfig(  # type: ignore[call-arg]
            env_secrets=["github-mcp-credentials", "watsonx-credentials"]
        )
        assert len(agent.env_secrets) == 2
