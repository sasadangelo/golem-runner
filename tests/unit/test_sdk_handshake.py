# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for golem_agent_sdk.handshake — perform_handshake().

Covers:
  - Skipped silently when cp_url is empty
  - POST is sent to the correct URL with the card payload
  - Warning logged (not raised) on HTTP error
  - Warning logged (not raised) on network error
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from golem_agent_sdk.handshake import perform_handshake

# ---------------------------------------------------------------------------
# Helper — a fake httpx.AsyncClient context manager
# ---------------------------------------------------------------------------


def _mock_client(*, status_code: int = 200, raise_exc: Exception | None = None) -> MagicMock:
    """Return a mock AsyncClient that simulates the given HTTP response."""
    response = MagicMock()
    response.status_code = status_code
    if raise_exc:
        response.raise_for_status.side_effect = raise_exc
    else:
        response.raise_for_status.return_value = None

    client = AsyncMock()
    client.post = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


# ---------------------------------------------------------------------------
# perform_handshake — skip when cp_url is empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handshake_skipped_when_no_cp_url() -> None:
    """perform_handshake must not make any HTTP call when cp_url is empty."""
    with patch("golem_agent_sdk.handshake.httpx.AsyncClient") as mock_cls:
        await perform_handshake(cp_url="", agent_id="a", card={})
    mock_cls.assert_not_called()


@pytest.mark.asyncio
async def test_handshake_skipped_for_empty_string() -> None:
    """An empty string cp_url must not trigger any HTTP call."""
    with patch("golem_agent_sdk.handshake.httpx.AsyncClient") as mock_cls:
        await perform_handshake(cp_url="", agent_id="a", card={})
    mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# perform_handshake — success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handshake_posts_to_correct_url() -> None:
    """POST must target /agents/{agent_id}/handshake on the Control Plane."""
    mock_client = _mock_client(status_code=200)
    with patch("golem_agent_sdk.handshake.httpx.AsyncClient", return_value=mock_client):
        await perform_handshake(cp_url="http://cp:9000", agent_id="my-agent", card={"id": "my-agent"})

    mock_client.post.assert_awaited_once()
    call_url = mock_client.post.call_args[0][0]
    assert call_url == "http://cp:9000/agents/my-agent/handshake"


@pytest.mark.asyncio
async def test_handshake_sends_card_payload() -> None:
    """The card dict must be sent as the 'card' key in the JSON body."""
    mock_client = _mock_client(status_code=200)
    card = {"id": "x", "name": "Agent X"}
    with patch("golem_agent_sdk.handshake.httpx.AsyncClient", return_value=mock_client):
        await perform_handshake(cp_url="http://cp:9000", agent_id="x", card=card)

    call_kwargs = mock_client.post.call_args[1]
    assert call_kwargs["json"] == {"card": card}


@pytest.mark.asyncio
async def test_handshake_strips_trailing_slash_from_cp_url() -> None:
    """Trailing slashes on cp_url must not result in a double-slash URL."""
    mock_client = _mock_client(status_code=200)
    with patch("golem_agent_sdk.handshake.httpx.AsyncClient", return_value=mock_client):
        await perform_handshake(cp_url="http://cp:9000/", agent_id="agent-1", card={})

    call_url = mock_client.post.call_args[0][0]
    assert "//" not in call_url.replace("http://", "")


# ---------------------------------------------------------------------------
# perform_handshake — error paths (must warn, never raise)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handshake_warns_on_http_error(caplog: pytest.LogCaptureFixture) -> None:
    """An HTTP error must be logged as a warning, not raised."""
    import httpx

    mock_client = _mock_client(raise_exc=httpx.HTTPStatusError("500", request=MagicMock(), response=MagicMock()))
    with patch("golem_agent_sdk.handshake.httpx.AsyncClient", return_value=mock_client):
        with caplog.at_level(logging.WARNING, logger="runner.handshake"):
            await perform_handshake(cp_url="http://cp:9000", agent_id="a", card={})

    assert any("Handshake" in r.message and "failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_handshake_warns_on_network_error(caplog: pytest.LogCaptureFixture) -> None:
    """A network error (ConnectError) must be logged as a warning, not raised."""
    import httpx

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))

    with patch("golem_agent_sdk.handshake.httpx.AsyncClient", return_value=mock_client):
        with caplog.at_level(logging.WARNING, logger="runner.handshake"):
            await perform_handshake(cp_url="http://cp:9000", agent_id="a", card={})

    assert any("Handshake" in r.message and "failed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_handshake_does_not_raise_on_error() -> None:
    """perform_handshake must never propagate any exception to the caller."""
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(side_effect=RuntimeError("unexpected"))

    with patch("golem_agent_sdk.handshake.httpx.AsyncClient", return_value=mock_client):
        # Should complete without raising
        await perform_handshake(cp_url="http://cp:9000", agent_id="a", card={})
