# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Unit tests for Automation management endpoints.

Covers:
  - POST /a2a/automations       register cron / timer / webhook
  - GET  /a2a/automations       list all automations
  - GET  /a2a/automations/{id}  retrieve a single automation
  - DELETE /a2a/automations/{id} remove an automation
  - 404 on unknown automation ID
  - 422 on invalid payload
"""

import sys
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client_with_scheduler() -> Generator[TestClient, None, None]:
    """TestClient with a real AutomationScheduler (asyncio tasks do not
    actually run — we only test the HTTP layer and in-memory state).

    Uses TestClient as a context manager so the FastAPI lifespan runs and
    ``automation_scheduler`` is set before the test issues any requests.
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
        patch("golem_agent_sdk.handshake.perform_handshake", side_effect=_noop_handshake),
    ):
        import main as m

        from golem_agent_sdk.router import task_store

        task_store.clear()

        with TestClient(m.app) as client:
            yield client


# ---------------------------------------------------------------------------
# Helper — build a valid automation request body
# ---------------------------------------------------------------------------


def _timer_body(task_input: str = "ping", interval: int = 60, name: str = "") -> dict:
    return {"name": name, "task_input": task_input, "trigger": {"type": "timer", "interval_seconds": interval}}


def _cron_body(task_input: str = "check", cron: str = "*/5 * * * *", name: str = "") -> dict:
    return {"name": name, "task_input": task_input, "trigger": {"type": "cron", "cron": cron}}


def _webhook_body(task_input: str = "handle: {body}", path: str = "/webhooks/test", name: str = "") -> dict:
    return {"name": name, "task_input": task_input, "trigger": {"type": "webhook", "path": path}}


# ---------------------------------------------------------------------------
# POST /a2a/automations — create
# ---------------------------------------------------------------------------


def test_create_timer_automation(client_with_scheduler: TestClient) -> None:
    """POST /a2a/automations with a timer trigger must return 201."""
    resp = client_with_scheduler.post("/a2a/automations", json=_timer_body("ping", 60))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["trigger_type"] == "timer"
    assert body["interval_seconds"] == 60
    assert body["task_input"] == "ping"
    assert body["enabled"] is True
    assert body["automation_id"].startswith("auto-")


def test_create_cron_automation(client_with_scheduler: TestClient) -> None:
    """POST /a2a/automations with a cron trigger must return 201 with cron field."""
    resp = client_with_scheduler.post("/a2a/automations", json=_cron_body("health check", "*/5 * * * *"))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["trigger_type"] == "cron"
    assert body["cron"] == "*/5 * * * *"
    assert body["task_input"] == "health check"


def test_create_webhook_automation(client_with_scheduler: TestClient) -> None:
    """POST /a2a/automations with a webhook trigger must return 201 with path field."""
    resp = client_with_scheduler.post("/a2a/automations", json=_webhook_body("handle: {body}", "/webhooks/test"))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["trigger_type"] == "webhook"
    assert body["path"] == "/webhooks/test"
    assert body["task_input"] == "handle: {body}"


def test_create_automation_with_name(client_with_scheduler: TestClient) -> None:
    """An optional name is stored and returned."""
    resp = client_with_scheduler.post("/a2a/automations", json=_timer_body(name="my-automation"))
    assert resp.status_code == 201, resp.text
    assert resp.json()["name"] == "my-automation"


def test_create_automation_missing_task_input_returns_422(client_with_scheduler: TestClient) -> None:
    """Omitting task_input must return 422."""
    resp = client_with_scheduler.post(
        "/a2a/automations",
        json={"trigger": {"type": "timer", "interval_seconds": 10}},
    )
    assert resp.status_code == 422


def test_create_automation_invalid_trigger_type_returns_422(client_with_scheduler: TestClient) -> None:
    """An unrecognised trigger type must return 422."""
    resp = client_with_scheduler.post(
        "/a2a/automations",
        json={"task_input": "x", "trigger": {"type": "unknown"}},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /a2a/automations — list
# ---------------------------------------------------------------------------


def test_list_automations(client_with_scheduler: TestClient) -> None:
    """GET /a2a/automations must list all registered automations."""
    client_with_scheduler.post("/a2a/automations", json=_timer_body("t1", 10))
    client_with_scheduler.post("/a2a/automations", json=_timer_body("t2", 20))
    resp = client_with_scheduler.get("/a2a/automations")
    assert resp.status_code == 200
    ids = {a["automation_id"] for a in resp.json()}
    assert len(ids) >= 2


# ---------------------------------------------------------------------------
# GET /a2a/automations/{id} — get single
# ---------------------------------------------------------------------------


def test_get_automation(client_with_scheduler: TestClient) -> None:
    """GET /a2a/automations/{id} must return the correct automation."""
    created = client_with_scheduler.post("/a2a/automations", json=_timer_body("check", 5)).json()
    automation_id = created["automation_id"]

    resp = client_with_scheduler.get(f"/a2a/automations/{automation_id}")
    assert resp.status_code == 200
    assert resp.json()["automation_id"] == automation_id


def test_get_automation_not_found(client_with_scheduler: TestClient) -> None:
    """GET /a2a/automations/<unknown> must return 404."""
    resp = client_with_scheduler.get("/a2a/automations/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /a2a/automations/{id} — delete
# ---------------------------------------------------------------------------


def test_delete_automation(client_with_scheduler: TestClient) -> None:
    """DELETE /a2a/automations/{id} must return 204 and make GET return 404."""
    created = client_with_scheduler.post("/a2a/automations", json=_timer_body("bye", 3)).json()
    automation_id = created["automation_id"]

    del_resp = client_with_scheduler.delete(f"/a2a/automations/{automation_id}")
    assert del_resp.status_code == 204

    get_resp = client_with_scheduler.get(f"/a2a/automations/{automation_id}")
    assert get_resp.status_code == 404


def test_delete_automation_not_found(client_with_scheduler: TestClient) -> None:
    """DELETE /a2a/automations/<unknown> must return 404."""
    resp = client_with_scheduler.delete("/a2a/automations/ghost-id")
    assert resp.status_code == 404
