# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""OllamaClient — LLMClient implementation for the native Ollama REST API.

Config: ``llm.provider: ollama`` + ``llm.protocol: ollama``

Uses the ``langchain-ollama`` integration which talks directly to the Ollama
native API (``/api/chat``) rather than the OpenAI-compat layer.  This gives
access to Ollama-specific features (context window sizing, temperature, etc.)
without needing an API key.

Required fields in config.yaml:
  llm.model  — model identifier as shown in ``ollama list`` (e.g. "llama3", "mistral")
  llm.url    — Ollama base URL (default: "http://localhost:11434")

Optional:
  llm.max_new_tokens — default 2048
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from golem_framework.llm_gateway.base import LLMClient


class OllamaClient(LLMClient):
    """LLM Gateway adapter for the native Ollama REST API.

    Args:
        model:          Model identifier as shown in ``ollama list``.
        base_url:       Ollama server base URL (default: http://localhost:11434).
        max_new_tokens: Maximum tokens the model may generate per response.
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://localhost:11434",
        max_new_tokens: int = 2048,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._max_new_tokens = max_new_tokens

    def as_chat_model(self) -> BaseChatModel:
        """Return a configured ChatOllama instance.

        Returns:
            A ChatOllama model ready for ``.invoke()`` and ``.bind_tools()``.
        """
        return ChatOllama(
            model=self._model,
            base_url=self._base_url,
            num_predict=self._max_new_tokens,
        )
