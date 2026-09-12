# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""LLM Gateway factory — selects the correct LLMClient from config.

The selection logic is: provider + protocol → concrete client class.

Supported combinations
----------------------
  provider=watsonx,  protocol=watsonx → WatsonxClient
  provider=openai,   protocol=openai  → OpenAIClient
  provider=ollama,   protocol=openai  → OpenAIClient   (Ollama /v1 compat layer)
  provider=ollama,   protocol=ollama  → OllamaClient   (native Ollama API)
  provider=vllm,     protocol=openai  → OpenAIClient
  provider=lmstudio, protocol=openai  → OpenAIClient

Adding a new provider: implement LLMClient in a new module, add a branch here.
"""

from __future__ import annotations

import logging

from golem_framework.llm_gateway.base import LLMClient

logger = logging.getLogger("runner.llm_gateway")


def build_llm_client(
    *,
    provider: str,
    protocol: str,
    model: str,
    url: str,
    api_key: str | None = None,
    project_id: str = "",
    max_new_tokens: int = 2048,
) -> LLMClient:
    """Instantiate the correct LLMClient for the given provider and protocol.

    Args:
        provider:       Provider name from ``llm.provider`` in config.yaml
                        (e.g. "watsonx", "ollama", "openai", "vllm").
        protocol:       Protocol/integration name from ``llm.protocol``
                        (e.g. "watsonx", "openai", "ollama").
        model:          Model identifier (provider-specific format).
        url:            Service endpoint URL.
        api_key:        API key or token (None / empty for local servers).
        project_id:     WatsonX project UUID (only required for provider=watsonx).
        max_new_tokens: Maximum tokens the model may generate per response.

    Returns:
        A ready-to-use LLMClient instance.

    Raises:
        ValueError: If the provider+protocol combination is not supported.
    """
    p = provider.lower().strip()
    proto = protocol.lower().strip()

    logger.info("LLM Gateway: provider=%s protocol=%s model=%s", p, proto, model)

    if p == "watsonx" and proto == "watsonx":
        from golem_framework.llm_gateway.watsonx import WatsonxClient

        return WatsonxClient(
            model=model,
            url=url,
            project_id=project_id,
            api_key=api_key,
            max_new_tokens=max_new_tokens,
        )

    if proto == "openai":
        from golem_framework.llm_gateway.openai import OpenAIClient

        return OpenAIClient(
            model=model,
            base_url=url,
            api_key=api_key,
            max_new_tokens=max_new_tokens,
        )

    if p == "ollama" and proto == "ollama":
        from golem_framework.llm_gateway.ollama import OllamaClient

        return OllamaClient(
            model=model,
            base_url=url,
            max_new_tokens=max_new_tokens,
        )

    raise ValueError(
        f"Unsupported LLM provider/protocol combination: provider={p!r} protocol={proto!r}. "
        "Supported combinations: watsonx/watsonx, */openai, ollama/ollama."
    )
