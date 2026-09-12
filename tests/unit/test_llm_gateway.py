# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for golem_framework.llm_gateway.

All LangChain provider clients (ChatWatsonx, ChatOpenAI, ChatOllama) are
mocked by conftest, so no credentials or running services are required.

Covers:
  - LLMClient is abstract — cannot be instantiated directly
  - build_llm_client() returns the correct client class for each combination
  - build_llm_client() raises ValueError for unsupported combinations
  - WatsonxClient.as_chat_model() calls ChatWatsonx with correct params
  - OpenAIClient.as_chat_model() calls ChatOpenAI with correct params
  - OllamaClient.as_chat_model() calls ChatOllama with correct params
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# LLMClient ABC
# ---------------------------------------------------------------------------


def test_llm_client_is_abstract() -> None:
    """LLMClient cannot be instantiated — it is an ABC."""
    from golem_framework.llm_gateway.base import LLMClient

    with pytest.raises(TypeError):
        LLMClient()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# build_llm_client — routing logic
# ---------------------------------------------------------------------------


class TestBuildLlmClient:
    """build_llm_client() routes to the correct concrete class."""

    def test_watsonx_watsonx(self) -> None:
        from golem_framework.llm_gateway.factory import build_llm_client
        from golem_framework.llm_gateway.watsonx import WatsonxClient

        client = build_llm_client(
            provider="watsonx",
            protocol="watsonx",
            model="llama3",
            url="https://watsonx",
            project_id="proj-1",
        )
        assert isinstance(client, WatsonxClient)

    def test_openai_openai(self) -> None:
        from golem_framework.llm_gateway.factory import build_llm_client
        from golem_framework.llm_gateway.openai import OpenAIClient

        client = build_llm_client(
            provider="openai",
            protocol="openai",
            model="gpt-4o",
            url="https://api.openai.com/v1",
        )
        assert isinstance(client, OpenAIClient)

    def test_ollama_openai_compat(self) -> None:
        """Ollama via OpenAI-compat layer → OpenAIClient."""
        from golem_framework.llm_gateway.factory import build_llm_client
        from golem_framework.llm_gateway.openai import OpenAIClient

        client = build_llm_client(
            provider="ollama",
            protocol="openai",
            model="llama3",
            url="http://localhost:11434/v1",
        )
        assert isinstance(client, OpenAIClient)

    def test_vllm_openai(self) -> None:
        """vLLM with OpenAI compat → OpenAIClient."""
        from golem_framework.llm_gateway.factory import build_llm_client
        from golem_framework.llm_gateway.openai import OpenAIClient

        client = build_llm_client(
            provider="vllm",
            protocol="openai",
            model="mistral",
            url="http://vllm:8000/v1",
        )
        assert isinstance(client, OpenAIClient)

    def test_ollama_native(self) -> None:
        """Ollama native API → OllamaClient."""
        from golem_framework.llm_gateway.factory import build_llm_client
        from golem_framework.llm_gateway.ollama import OllamaClient

        client = build_llm_client(
            provider="ollama",
            protocol="ollama",
            model="llama3",
            url="http://localhost:11434",
        )
        assert isinstance(client, OllamaClient)

    def test_provider_case_insensitive(self) -> None:
        """Provider and protocol strings are normalised to lowercase."""
        from golem_framework.llm_gateway.factory import build_llm_client
        from golem_framework.llm_gateway.watsonx import WatsonxClient

        client = build_llm_client(
            provider="WatsonX",
            protocol="WatsonX",
            model="m",
            url="http://u",
            project_id="p",
        )
        assert isinstance(client, WatsonxClient)

    def test_unsupported_combination_raises(self) -> None:
        """Unknown provider+protocol raises ValueError."""
        from golem_framework.llm_gateway.factory import build_llm_client

        with pytest.raises(ValueError, match="Unsupported"):
            build_llm_client(
                provider="groq",
                protocol="groq",
                model="m",
                url="http://u",
            )


# ---------------------------------------------------------------------------
# WatsonxClient
# ---------------------------------------------------------------------------


class TestWatsonxClient:
    """WatsonxClient.as_chat_model() instantiates ChatWatsonx with correct args."""

    def test_as_chat_model_returns_mock(self) -> None:
        """as_chat_model() must return the ChatWatsonx instance."""
        from golem_framework.llm_gateway.watsonx import WatsonxClient

        mock_model = MagicMock()
        with patch("golem_framework.llm_gateway.watsonx.ChatWatsonx", return_value=mock_model) as mock_cls:
            client = WatsonxClient(
                model="llama3",
                url="https://us-south.ml.cloud.ibm.com",
                project_id="proj-123",
                api_key="secret",
            )
            result = client.as_chat_model()

        mock_cls.assert_called_once()
        assert result is mock_model

    def test_as_chat_model_passes_model_id(self) -> None:
        """model_id must be forwarded to ChatWatsonx."""
        from golem_framework.llm_gateway.watsonx import WatsonxClient

        with patch("golem_framework.llm_gateway.watsonx.ChatWatsonx") as mock_cls:
            WatsonxClient(
                model="granite-13b",
                url="https://u",
                project_id="p",
                api_key=None,
            ).as_chat_model()

        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["model_id"] == "granite-13b"

    def test_as_chat_model_passes_max_tokens(self) -> None:
        """max_new_tokens must appear in the params dict."""
        from golem_framework.llm_gateway.watsonx import WatsonxClient

        with patch("golem_framework.llm_gateway.watsonx.ChatWatsonx") as mock_cls:
            WatsonxClient(
                model="m",
                url="u",
                project_id="p",
                api_key=None,
                max_new_tokens=512,
            ).as_chat_model()

        params = mock_cls.call_args[1]["params"]
        assert params["max_tokens"] == 512


# ---------------------------------------------------------------------------
# OpenAIClient
# ---------------------------------------------------------------------------


class TestOpenAIClient:
    """OpenAIClient.as_chat_model() instantiates ChatOpenAI with correct args."""

    def test_as_chat_model_returns_mock(self) -> None:
        from golem_framework.llm_gateway.openai import OpenAIClient

        mock_model = MagicMock()
        with patch("golem_framework.llm_gateway.openai.ChatOpenAI", return_value=mock_model) as mock_cls:
            result = OpenAIClient(model="gpt-4o", base_url="https://api.openai.com/v1", api_key="sk-x").as_chat_model()

        mock_cls.assert_called_once()
        assert result is mock_model

    def test_as_chat_model_passes_base_url(self) -> None:
        from golem_framework.llm_gateway.openai import OpenAIClient

        with patch("golem_framework.llm_gateway.openai.ChatOpenAI") as mock_cls:
            OpenAIClient(model="m", base_url="http://vllm:8000/v1", api_key=None).as_chat_model()

        assert mock_cls.call_args[1]["base_url"] == "http://vllm:8000/v1"

    def test_none_api_key_defaults_to_no_key(self) -> None:
        """None api_key must not cause a crash — defaults to 'no-key'."""
        from golem_framework.llm_gateway.openai import OpenAIClient

        with patch("golem_framework.llm_gateway.openai.ChatOpenAI"):
            OpenAIClient(model="m", base_url="http://x", api_key=None).as_chat_model()


# ---------------------------------------------------------------------------
# OllamaClient
# ---------------------------------------------------------------------------


class TestOllamaClient:
    """OllamaClient.as_chat_model() instantiates ChatOllama with correct args."""

    def test_as_chat_model_returns_mock(self) -> None:
        from golem_framework.llm_gateway.ollama import OllamaClient

        mock_model = MagicMock()
        with patch("golem_framework.llm_gateway.ollama.ChatOllama", return_value=mock_model) as mock_cls:
            result = OllamaClient(model="llama3").as_chat_model()

        mock_cls.assert_called_once()
        assert result is mock_model

    def test_default_base_url(self) -> None:
        """Default base_url must be http://localhost:11434."""
        from golem_framework.llm_gateway.ollama import OllamaClient

        with patch("golem_framework.llm_gateway.ollama.ChatOllama") as mock_cls:
            OllamaClient(model="llama3").as_chat_model()

        assert mock_cls.call_args[1]["base_url"] == "http://localhost:11434"

    def test_custom_base_url(self) -> None:
        from golem_framework.llm_gateway.ollama import OllamaClient

        with patch("golem_framework.llm_gateway.ollama.ChatOllama") as mock_cls:
            OllamaClient(model="llama3", base_url="http://ollama-server:11434").as_chat_model()

        assert mock_cls.call_args[1]["base_url"] == "http://ollama-server:11434"

    def test_max_new_tokens_forwarded(self) -> None:
        from golem_framework.llm_gateway.ollama import OllamaClient

        with patch("golem_framework.llm_gateway.ollama.ChatOllama") as mock_cls:
            OllamaClient(model="llama3", max_new_tokens=1024).as_chat_model()

        assert mock_cls.call_args[1]["num_predict"] == 1024
