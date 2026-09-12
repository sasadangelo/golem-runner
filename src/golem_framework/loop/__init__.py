# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""golem-framework loop sub-package.

Exports the AgentLoop ABC and the built-in LangGraphLoop implementation.
"""

from .base import AgentLoop
from .langgraph import LangGraphLoop

__all__ = ["AgentLoop", "LangGraphLoop"]
