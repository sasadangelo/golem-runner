# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""OpenAIClient — LLMClient implementation for any OpenAI-compatible endpoint.

Config: ``llm.protocol: openai``

Works with any server that speaks the OpenAI Chat Completions REST API:
  - Public OpenAI (api.openai.com)
  - vLLM   (http://host:8000/v1)
  - LM Studio (http://localhost:1234/v1)
  - Ollama OpenAI-compat layer (http://localhost:11434/v1)

Required fields in config.yaml / env:
  llm.model    — model identifier (e.g. "gpt-4o", "llama3", "mistral")
  llm.url      — base URL of the OpenAI-compatible server (e.g. "http://localhost:11434/v1")
  OPENAI_API_KEY — injected from env; use "ollama" or any non-empty string for local servers

Optional:
  llm.max_new_tokens — default 2048
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from golem_framework.llm_gateway.base import LLMClient


class OpenAIClient(LLMClient):
    """LLM Gateway adapter for any OpenAI-compatible endpoint.

    Args:
        model:          Model identifier (e.g. "gpt-4o", "llama3").
        base_url:       Base URL of the OpenAI-compatible server.
        api_key:        API key (any non-empty string works for local servers).
        max_new_tokens: Maximum tokens the model may generate per response.
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str | None,
        max_new_tokens: int = 2048,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._api_key = api_key or "no-key"
        self._max_new_tokens = max_new_tokens

    def as_chat_model(self) -> BaseChatModel:
        """Return a configured ChatOpenAI instance pointing to the given base URL.

        Returns:
            A ChatOpenAI model ready for ``.invoke()`` and ``.bind_tools()``.
        """
        return ChatOpenAI(
            model=self._model,
            base_url=self._base_url,
            api_key=self._api_key,
            max_tokens=self._max_new_tokens,
        )
