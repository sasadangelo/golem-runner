# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""A2A startup handshake for golem-agent-sdk.

The handshake pushes this agent's Card to the Control Plane via
``POST /agents/{id}/handshake`` so the broker can register it as an
available peer.  The function is intentionally fire-and-warn: a failure
never blocks runner startup — the Control Plane can always pull the card
from ``/.well-known/agent.json`` later.

No LLM dependency — any agent (LLM-backed or pure A2A proxy) can use this.

Typical usage
-------------
    from golem_agent_sdk.handshake import perform_handshake

    await perform_handshake(
        cp_url="http://golem-cp:9000",
        agent_id="my-agent-001",
        card=agent_card.to_dict(),
    )
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger("runner.handshake")


async def perform_handshake(
    *,
    cp_url: str,
    agent_id: str,
    card: dict,
    timeout: float = 10.0,
) -> None:
    """Push the Agent Card to the Control Plane broker.

    Silently skipped when ``cp_url`` is empty (local dev / standalone mode).
    On network or HTTP error, a warning is logged but the exception is
    swallowed so runner startup is never blocked.

    Args:
        cp_url:    Control Plane base URL (e.g. "http://golem-cp:9000").
                   Pass an empty string to skip the handshake entirely.
        agent_id:  Unique identifier of this agent — used to build the URL
                   path ``/agents/{agent_id}/handshake``.
        card:      The Agent Card as a plain dict (from ``AgentCard.to_dict()``).
        timeout:   HTTP request timeout in seconds (default: 10.0).
    """
    if not cp_url:
        logger.debug("No cp_url configured — skipping handshake (standalone mode).")
        return

    url = f"{cp_url.rstrip('/')}/agents/{agent_id}/handshake"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json={"card": card})
            response.raise_for_status()
        logger.info("Handshake completed with Control Plane at %s", cp_url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Handshake with Control Plane failed (will rely on pull): %s", exc)
