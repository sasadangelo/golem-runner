# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""golem-framework LLM Gateway — provider/protocol abstraction.

Exports the LLMClient ABC and the build_llm_client() factory.
Concrete clients (WatsonxClient, OpenAIClient, OllamaClient) are imported
lazily by the factory so missing optional dependencies only fail at boot
if the selected provider actually requires them.
"""

from .base import LLMClient
from .factory import build_llm_client

__all__ = ["LLMClient", "build_llm_client"]
