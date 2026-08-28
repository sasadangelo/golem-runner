# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""A2A delegation tool — lets an agent delegate a sub-task to another agent
via the Control Plane broker.

The runner never talks directly to another runner pod.  All inter-agent
communication goes through the Control Plane endpoint:

    POST /agents/{source_id}/delegate
    Body: {"target_agent_id": "...", "message": "..."}

After the Control Plane returns a task_id (fire-and-forget), this tool polls
GET /agents/{source_id}/delegate/{task_id} until the task reaches a terminal
state (completed / failed) or the delegation_timeout_seconds is exceeded.

This keeps every runner fully isolated from the cluster topology.
"""

import logging
import time

import httpx
from core.config import settings
from langchain_core.tools import tool

logger = logging.getLogger("runner.a2a")

_POLL_INTERVAL: float = 3.0  # seconds between status polls


@tool
def delegate_to_agent(target_agent_id: str, message: str) -> str:
    """Delegate a sub-task to another specialised agent via the Control Plane.

    Use this tool when you need another agent to handle a specific part of
    the work — for example, delegating report writing to a Report-Writer agent
    after completing your own analysis.

    The tool submits the task (fire-and-forget) and then polls the Control Plane
    until the task completes or the delegation timeout is reached.

    Args:
        target_agent_id: The unique ID of the target agent (must be registered
                         in the Control Plane, e.g. 'report-writer-001').
        message:         The full instruction text to send to the target agent.

    Returns:
        The result produced by the target agent, or an error message if the
        delegation failed or timed out.
    """
    cp_url = settings.agent.cp_url.rstrip("/")
    if not cp_url:
        return "ERROR: agent.cp_url is not configured — cannot delegate tasks."

    source_id = settings.agent.id
    delegate_url = f"{cp_url}/agents/{source_id}/delegate"
    timeout_seconds: int = settings.agent.delegation_timeout_seconds

    # ------------------------------------------------------------------
    # Step 1 — submit the task (fire-and-forget, expects 202)
    # ------------------------------------------------------------------
    try:
        resp = httpx.post(
            delegate_url,
            json={"target_agent_id": target_agent_id, "message": message, "source": "a2a"},
            timeout=30,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200]
        logger.warning("Delegation to %s failed (HTTP %d): %s", target_agent_id, exc.response.status_code, detail)
        return f"ERROR: delegation to {target_agent_id} failed (HTTP {exc.response.status_code}): {detail}"
    except httpx.HTTPError as exc:
        logger.warning("Delegation to %s unreachable: %s", target_agent_id, exc)
        return f"ERROR: could not reach Control Plane at {cp_url}: {exc}"

    data = resp.json()
    task_id: str = data.get("task_id", "unknown")
    logger.info("Delegated task %s to agent %s — polling for result (timeout=%ds)", task_id, target_agent_id, timeout_seconds)

    # ------------------------------------------------------------------
    # Step 2 — poll until terminal state or timeout
    # ------------------------------------------------------------------
    poll_url = f"{cp_url}/agents/{target_agent_id}/tasks/{task_id}"
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        time.sleep(_POLL_INTERVAL)
        try:
            poll_resp = httpx.get(poll_url, timeout=10)
            poll_resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Poll for task %s failed: %s — retrying", task_id, exc)
            continue

        task_data = poll_resp.json()
        status = task_data.get("status", "")
        logger.info("Task %s status=%s", task_id, status)

        if status == "completed":
            result = task_data.get("result") or "(no result)"
            return f"Delegated task {task_id} completed by {target_agent_id}:\n{result}"
        if status == "failed":
            reason = task_data.get("result") or "(unknown error)"
            return f"ERROR: delegated task {task_id} failed on {target_agent_id}: {reason}"

    return f"ERROR: delegated task {task_id} to {target_agent_id} did not complete within {timeout_seconds}s."
