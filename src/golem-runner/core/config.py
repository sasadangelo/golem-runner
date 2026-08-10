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

import os
from pathlib import Path
from typing import Any, ClassVar

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Section: agent
# ---------------------------------------------------------------------------


class AgentConfig(BaseSettings):
    """Agent identity and runtime parameters."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="AGENT_",
        extra="ignore",
    )

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
    enabled_skill: str = Field(
        default="bash,http_check",
        description="Comma-separated list of skills to enable (e.g. 'bash,http_check').",
    )
    cp_url: str = Field(
        default="",
        description="Control Plane base URL for handshake registration (e.g. http://golem-cp:9000). "
                    "Leave empty to skip handshake (useful for local dev without a Control Plane).",
    )


# ---------------------------------------------------------------------------
# Section: llm
# ---------------------------------------------------------------------------


class LLMConfig(BaseSettings):
    """LLM provider and model parameters."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        extra="ignore",
    )

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
    # Secret — populated from WATSONX_API_KEY in model_post_init, never from YAML.
    api_key: SecretStr | None = Field(
        default=None,
        description="WatsonX API key (injected from WATSONX_API_KEY env var).",
    )


# ---------------------------------------------------------------------------
# Root Settings
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Root configuration object. Import ``settings`` — never instantiate directly."""

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        yaml_file=str(Path(__file__).parent.parent / "config.yaml"),
        env_file=str(Path(__file__).parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    agent: AgentConfig = Field(default_factory=AgentConfig, description="Agent section.")
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM section.")

    def model_post_init(self, __context: Any) -> None:  # noqa: ANN401
        api_key = os.getenv("WATSONX_API_KEY")
        if api_key:
            self.llm.api_key = SecretStr(api_key)


# Single source of truth — import this everywhere, never call Settings() again.
settings: Settings = Settings()
