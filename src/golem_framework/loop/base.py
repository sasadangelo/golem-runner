# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""AgentLoop — abstract base class for agentic execution loops.

Any concrete loop (LangGraph, AutoGen, CrewAI …) must implement this ABC so
the runner can swap implementations without touching its own code.

The only contract the runner depends on is:
  - ``build()``   → compile the loop at startup (called once during lifespan)
  - ``invoke()``  → synchronous single-turn execution (used by the A2A executor adapter)
  - ``astream_events()`` → async token-by-token streaming (used by the WS chat endpoint)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class AgentLoop(ABC):
    """Abstract contract for an agentic execution loop.

    Concrete implementations (e.g. LangGraphLoop) compile their internal
    graph in ``build()`` and expose both a synchronous ``invoke()`` for
    fire-and-forget A2A tasks and an async ``astream_events()`` for
    WebSocket streaming chat.
    """

    @abstractmethod
    def build(self) -> None:
        """Compile and initialise the loop.

        Called once during application lifespan after all tools and MCP
        servers have been loaded.  Implementations should raise on any
        fatal configuration error so the runner fails fast at boot.
        """

    @abstractmethod
    def invoke(self, messages: list[dict[str, Any]]) -> str:
        """Execute a single turn synchronously and return the final reply.

        Runs in a thread-pool executor so the asyncio event loop is never
        blocked.  The caller passes a list of message dicts in the LangChain
        wire format (``{"role": "human"|"ai"|"system", "content": "..."}``)
        and receives the plain-text reply produced by the loop.

        Args:
            messages: Ordered list of conversation turns.

        Returns:
            The agent's final plain-text reply for this turn.
        """

    @abstractmethod
    def astream_events(
        self,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield LangChain-style stream events for a single turn asynchronously.

        Used by the WebSocket chat endpoint to forward token chunks to the
        client in real time.  The event dict shape must be compatible with
        LangChain's ``astream_events`` v2 format so the runner's WS handler
        can stay framework-agnostic.

        Args:
            messages: Ordered list of conversation turns.
            **kwargs: Additional arguments forwarded to the underlying engine
                      (e.g. ``config={"recursion_limit": 50}``).

        Yields:
            Event dicts with at minimum an ``"event"`` key.
        """
