# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""WatsonxClient — LLMClient implementation for IBM WatsonX.

Config: ``llm.provider: watsonx`` + ``llm.protocol: watsonx``

Required fields in config.yaml / env:
  llm.model       — e.g. "meta-llama/llama-3-3-70b-instruct"
  llm.url         — e.g. "https://us-south.ml.cloud.ibm.com"
  llm.project_id  — WatsonX project UUID
  WATSONX_API_KEY — injected from env; never in YAML

Optional:
  llm.max_new_tokens — default 2048
"""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_ibm import ChatWatsonx
from pydantic import SecretStr

from golem_framework.llm_gateway.base import LLMClient


class WatsonxClient(LLMClient):
    """LLM Gateway adapter for IBM WatsonX.

    Args:
        model:          WatsonX model identifier.
        url:            WatsonX service endpoint URL.
        project_id:     WatsonX project UUID.
        api_key:        WatsonX API key (resolved from env at construction time).
        max_new_tokens: Maximum tokens the model may generate per response.
    """

    def __init__(
        self,
        *,
        model: str,
        url: str,
        project_id: str,
        api_key: str | None,
        max_new_tokens: int = 2048,
    ) -> None:
        self._model = model
        self._url = url
        self._project_id = project_id
        self._api_key = api_key
        self._max_new_tokens = max_new_tokens

    def as_chat_model(self) -> BaseChatModel:
        """Return a configured ChatWatsonx instance.

        Returns:
            A ChatWatsonx model ready for ``.invoke()`` and ``.bind_tools()``.
        """
        return ChatWatsonx(
            model_id=self._model,
            url=SecretStr(self._url),
            project_id=self._project_id,
            api_key=self._api_key,
            params={"max_tokens": self._max_new_tokens},
        )
