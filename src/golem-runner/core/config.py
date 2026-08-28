"""Golem Runner — centralised Pydantic Settings configuration.

All non-secret parameters are loaded from ``config.yaml``.
Secrets (credentials, API keys) are loaded exclusively from ``.env`` /
environment variables and injected in ``model_post_init``.

Usage
-----
    from core.config import settings

    settings.agent.id
    settings.llm.model
    settings.llm.api_key      # injected from WATSONX_API_KEY
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, YamlConfigSettingsSource

# ---------------------------------------------------------------------------
# MCP server connection descriptor
# ---------------------------------------------------------------------------


class MCPServerConfig(BaseModel):
    """A single MCP server connection — URL plus optional per-server HTTP headers.

    Header values that start with ``$`` are resolved from environment variables
    at runtime (e.g. ``"$GITHUB_TOKEN"`` → ``os.environ["GITHUB_TOKEN"]``).
    Plain strings are used as-is.

    Both short form (bare URI string) and long form (this object) are accepted
    in ``agent.mcp_servers``; the short form is coerced to ``MCPServerConfig``
    automatically via the ``AgentConfig`` validator.
    """

    url: str
    headers: dict[str, str] = Field(default_factory=dict)

    def resolved_headers(self) -> dict[str, str]:
        """Return headers with ``$VAR`` placeholders substituted from env.

        Replaces every ``$VARNAME`` token in a header value with the
        corresponding environment variable.  Warns and substitutes an empty
        string when a referenced variable is not set.
        """
        import re

        _VAR_RE = re.compile(r"\$([A-Z_][A-Z0-9_]*)")

        out: dict[str, str] = {}
        for key, value in self.headers.items():
            def _replace(m: re.Match) -> str:  # noqa: ANN001
                env_var = m.group(1)
                resolved = os.environ.get(env_var)
                if resolved is None:
                    logging.getLogger("runner.mcp").warning(
                        "MCP header '%s' references env var '%s' which is not set", key, env_var
                    )
                    return ""
                return resolved

            out[key] = _VAR_RE.sub(_replace, value)
        return out


# ---------------------------------------------------------------------------
# Section: agent  (plain BaseModel — no env_prefix; env overrides applied in
#                  Settings.model_post_init so YAML never wins over env vars)
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """Agent identity and runtime parameters."""

    id: str = Field(default="golem-agent-001", description="Unique identifier for this agent instance.")
    name: str = Field(default="Golem Agent Runner", description="Human-readable agent name.")
    description: str = Field(
        default="Generic automation agent powered by Golem.",
        description="Short description shown in the A2A Agent Card.",
    )
    endpoint: str = Field(
        default="http://localhost:8001",
        description="Public endpoint of this agent container.",
    )
    system_prompt: str = Field(
        default="You are a helpful generic automation agent.",
        description="System prompt that defines the agent persona.",
    )
    enabled_skills: str = Field(
        default="bash,http_check",
        description="Comma-separated list of skills to enable (e.g. 'bash,http_check').",
    )
    cp_url: str = Field(
        default="",
        description="Control Plane base URL for handshake registration (e.g. http://golem-cp:9000). "
        "Leave empty to skip handshake (useful for local dev without a Control Plane).",
    )
    delegation_timeout_seconds: int = Field(
        default=300,
        description="Max seconds to wait for a delegated A2A task to complete. "
        "Used by the delegate skill when polling the target agent after fire-and-forget submission. "
        "Only relevant for agents that use the 'delegate' skill.",
    )
    mcp_servers: list[MCPServerConfig] = Field(
        default_factory=list,
        description="List of MCP servers to connect at boot. Each entry is either "
        "a plain URI string (no auth) or an object with 'url' and optional 'headers' "
        "(header values starting with '$' are resolved from env vars at runtime).",
    )
    env_secrets: list[str] = Field(
        default_factory=list,
        description="Names of K8s Secrets already present in the agent namespace to mount "
        "as envFrom in the pod (e.g. ['github-mcp-credentials']). "
        "The deploy.sh creates these secrets before calling golem agent create.",
    )
    triggers: list[dict] = Field(
        default_factory=list,
        description="Background triggers to start at boot. Each entry must have a 'type' field "
        "('cron', 'timer', or 'webhook') plus type-specific fields. "
        "Example: [{type: cron, cron: '*/30 * * * *', message: 'health-check /health'}]",
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_mcp_servers(cls, data: Any) -> Any:  # noqa: ANN401
        """Coerce bare URI strings in mcp_servers to MCPServerConfig dicts."""
        if isinstance(data, dict) and "mcp_servers" in data:
            coerced = []
            for entry in data["mcp_servers"]:
                if isinstance(entry, str):
                    coerced.append({"url": entry})
                else:
                    coerced.append(entry)
            data["mcp_servers"] = coerced
        return data


# ---------------------------------------------------------------------------
# Section: llm
# ---------------------------------------------------------------------------


class LLMConfig(BaseModel):
    """LLM provider and model parameters."""

    provider: str = Field(default="watsonx", description="LLM provider name.")
    protocol: str = Field(default="watsonx", description="LangChain protocol/integration to use.")
    model: str = Field(default="openai/gpt-oss-120b", description="Model identifier to load.")
    url: str = Field(
        default="https://us-south.ml.cloud.ibm.com",
        description="WatsonX service URL.",
    )
    project_id: str = Field(
        default="9def6989-c276-4042-8fc2-5b77a8e56ade",
        description="WatsonX project ID.",
    )
    max_new_tokens: int = Field(
        default=2048,
        description="Maximum number of tokens the model can generate in a single response "
        "(mapped to max_tokens in the WatsonX TextChatParameters).",
    )
    # Secret — populated from WATSONX_API_KEY in model_post_init, never from YAML.
    api_key: SecretStr | None = Field(
        default=None,
        description="WatsonX API key (injected from WATSONX_API_KEY env var).",
    )


# ---------------------------------------------------------------------------
# Root Settings
# ---------------------------------------------------------------------------

_CONFIG_YAML = Path(__file__).parent.parent / "config.yaml"
_ENV_FILE = Path(__file__).parent.parent / ".env"

# Mapping of AGENT_* env vars → AgentConfig field names
_AGENT_ENV_MAP: dict[str, str] = {
    "AGENT_ID": "id",
    "AGENT_NAME": "name",
    "AGENT_DESCRIPTION": "description",
    "AGENT_ENDPOINT": "endpoint",
    "AGENT_SYSTEM_PROMPT": "system_prompt",
    "AGENT_ENABLED_SKILLS": "enabled_skills",
    "AGENT_CP_URL": "cp_url",
}


class Settings(BaseSettings):
    """Root configuration object. Import ``settings`` — never instantiate directly."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        yaml_file=str(_CONFIG_YAML),
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    agent: AgentConfig = Field(default_factory=AgentConfig, description="Agent section.")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM section.")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Load order (highest → lowest priority):
        1. Init kwargs
        2. Environment variables  (AGENT_* applied later in model_post_init)
        3. .env file
        4. config.yaml
        """
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            YamlConfigSettingsSource(settings_cls),
        )

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        # Apply AGENT_* env var overrides — always win over config.yaml values.
        agent_overrides: dict[str, str] = {
            field: os.environ[env_var]
            for env_var, field in _AGENT_ENV_MAP.items()
            if env_var in os.environ
        }
        if agent_overrides:
            self.agent = self.agent.model_copy(update=agent_overrides)

        # Inject WATSONX_API_KEY — never from YAML.
        api_key = os.getenv("WATSONX_API_KEY")
        if api_key:
            self.llm = self.llm.model_copy(update={"api_key": SecretStr(api_key)})


# Single source of truth — import this everywhere, never call Settings() again.
settings: Settings = Settings()
