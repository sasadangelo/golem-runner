# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for background trigger management endpoints.

Covers:
  - POST /a2a/triggers       register cron / timer / webhook
  - GET  /a2a/triggers        list all triggers
  - GET  /a2a/triggers/{id}   retrieve a single trigger
  - DELETE /a2a/triggers/{id} remove a trigger
  - 404 on unknown trigger ID
"""

import sys
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_with_scheduler() -> Generator[TestClient, None, None]:
    """TestClient with a real TriggerScheduler (asyncio tasks do not actually
    run — we only test the HTTP layer and in-memory state).

    Uses TestClient as a context manager so the FastAPI lifespan runs and
    ``trigger_scheduler`` is set before the test issues any requests.
    """
    for mod in ("agent", "main"):
        sys.modules.pop(mod, None)

    async def _noop_handshake(*_a: object, **_kw: object) -> None:
        pass

    async def _noop_load_mcp_tools(*_a: object, **_kw: object) -> list:
        return []

    with (
        patch("agent.build_agent", return_value=MagicMock()),
        patch("main._load_mcp_tools", side_effect=_noop_load_mcp_tools),
        patch("main._register_with_control_plane", side_effect=_noop_handshake),
    ):
        import main as m

        from golem_agent_sdk.router import task_store
        task_store.clear()

        # Use context manager so lifespan runs and trigger_scheduler is initialised.
        with TestClient(m.app) as client:
            yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_create_timer_trigger(client_with_scheduler: TestClient) -> None:
    """POST /a2a/triggers with type=timer must return 201 and the trigger record."""
    resp = client_with_scheduler.post(
        "/a2a/triggers",
        json={"type": "timer", "interval_seconds": 60, "message": "ping"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "timer"
    assert body["interval_seconds"] == 60
    assert body["message"] == "ping"
    assert body["enabled"] is True
    assert "id" in body


def test_create_cron_trigger(client_with_scheduler: TestClient) -> None:
    """POST /a2a/triggers with type=cron must return 201 and include the cron field."""
    resp = client_with_scheduler.post(
        "/a2a/triggers",
        json={"type": "cron", "cron": "*/5 * * * *", "message": "health check"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "cron"
    assert body["cron"] == "*/5 * * * *"


def test_create_webhook_trigger(client_with_scheduler: TestClient) -> None:
    """POST /a2a/triggers with type=webhook must return 201 and include the path."""
    resp = client_with_scheduler.post(
        "/a2a/triggers",
        json={"type": "webhook", "path": "/webhooks/test", "message": "body={body}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "webhook"
    assert body["path"] == "/webhooks/test"


def test_list_triggers(client_with_scheduler: TestClient) -> None:
    """GET /a2a/triggers must list all registered triggers."""
    client_with_scheduler.post(
        "/a2a/triggers",
        json={"type": "timer", "interval_seconds": 10, "message": "t1"},
    )
    client_with_scheduler.post(
        "/a2a/triggers",
        json={"type": "timer", "interval_seconds": 20, "message": "t2"},
    )
    resp = client_with_scheduler.get("/a2a/triggers")
    assert resp.status_code == 200
    # At least the two we just created (may include others from previous tests
    # if the scheduler is shared, but the fixture resets the module).
    ids = {t["id"] for t in resp.json()}
    assert len(ids) >= 2


def test_get_trigger(client_with_scheduler: TestClient) -> None:
    """GET /a2a/triggers/{id} must return the correct trigger."""
    created = client_with_scheduler.post(
        "/a2a/triggers",
        json={"type": "timer", "interval_seconds": 5, "message": "check"},
    ).json()
    trigger_id = created["id"]

    resp = client_with_scheduler.get(f"/a2a/triggers/{trigger_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == trigger_id


def test_get_trigger_not_found(client_with_scheduler: TestClient) -> None:
    """GET /a2a/triggers/<unknown> must return 404."""
    resp = client_with_scheduler.get("/a2a/triggers/nonexistent-id")
    assert resp.status_code == 404


def test_delete_trigger(client_with_scheduler: TestClient) -> None:
    """DELETE /a2a/triggers/{id} must remove the trigger (204) and make GET return 404."""
    created = client_with_scheduler.post(
        "/a2a/triggers",
        json={"type": "timer", "interval_seconds": 3, "message": "bye"},
    ).json()
    trigger_id = created["id"]

    del_resp = client_with_scheduler.delete(f"/a2a/triggers/{trigger_id}")
    assert del_resp.status_code == 204

    get_resp = client_with_scheduler.get(f"/a2a/triggers/{trigger_id}")
    assert get_resp.status_code == 404


def test_delete_trigger_not_found(client_with_scheduler: TestClient) -> None:
    """DELETE /a2a/triggers/<unknown> must return 404."""
    resp = client_with_scheduler.delete("/a2a/triggers/ghost-id")
    assert resp.status_code == 404


def test_invalid_trigger_type_returns_422(client_with_scheduler: TestClient) -> None:
    """POST /a2a/triggers with an unknown type must return 422."""
    resp = client_with_scheduler.post(
        "/a2a/triggers",
        json={"type": "unknown", "message": "x"},
    )
    assert resp.status_code == 422
