# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""LLMClient — abstract base class for LLM provider adapters.

Every concrete gateway (WatsonX, OpenAI-compatible, Ollama) must implement
this ABC so LangGraphLoop stays completely provider-agnostic.

The only contract the loop depends on is ``as_chat_model()`` — it returns
a LangChain ``BaseChatModel`` that the graph can call with ``.invoke()``
and ``.bind_tools()``.  This keeps the gateway thin: it is purely a factory
for the LangChain chat model object; all graph logic lives in the loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel


class LLMClient(ABC):
    """Abstract factory for a LangChain-compatible chat model.

    Concrete subclasses encapsulate all provider-specific initialisation
    (credentials, URL, model name, parameter mapping) and expose a single
    ``as_chat_model()`` method that the loop uses to build the graph.
    """

    @abstractmethod
    def as_chat_model(self) -> BaseChatModel:
        """Return a ready-to-use LangChain BaseChatModel instance.

        The returned model must support:
          - ``.invoke(messages)`` — synchronous single-turn execution.
          - ``.bind_tools(tools)`` — tool-calling schema binding.
          - ``.astream_events(...)`` — async streaming (via LangGraph graph).

        Returns:
            A configured BaseChatModel for this provider and protocol.
        """
