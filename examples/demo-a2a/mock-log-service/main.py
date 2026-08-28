# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Mock log service for the demo-a2a example.

Simulates an application that produces structured logs and can be put into
a degraded state to generate error entries.

Endpoints:
  GET  /health          — overall service health (200 / 503)
  GET  /logs            — last N log entries as JSON
  POST /admin/inject-errors   — inject HTTP 500 error entries into the log
  POST /admin/clear-errors    — clear injected errors and restore healthy state
"""

import random
import time

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app: FastAPI = FastAPI(title="Mock Log Service", version="1.0.0")

# In-memory log store — populated at startup and updated by admin endpoints.
_logs: list[dict] = []
_error_mode: bool = False

_SERVICES = ["payment-service", "auth-service", "order-service", "inventory-service"]
_ERROR_PATHS = ["/api/checkout", "/api/login", "/api/orders", "/api/stock"]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _seed_healthy_logs() -> None:
    """Populate the log store with a baseline of healthy entries."""
    for i in range(20):
        _logs.append({
            "timestamp": _now(),
            "level": "INFO",
            "service": random.choice(_SERVICES),
            "method": "GET",
            "path": "/api/health",
            "status": 200,
            "latency_ms": random.randint(12, 80),
            "message": "Request completed successfully.",
        })


_seed_healthy_logs()


@app.get("/health")
def health() -> dict:
    """Return service health — 503 when error mode is active."""
    if _error_mode:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "error_mode": True},
        )
    return {"status": "ok", "error_mode": False}


@app.get("/logs")
def get_logs(limit: int = 50) -> dict:
    """Return the last ``limit`` log entries."""
    return {"count": min(limit, len(_logs)), "entries": _logs[-limit:]}


@app.post("/admin/inject-errors")
def inject_errors(count: int = 10) -> dict:
    """Inject ``count`` HTTP 500 error entries and activate error mode."""
    global _error_mode  # noqa: PLW0603
    _error_mode = True
    for _ in range(count):
        service = random.choice(_SERVICES)
        path = random.choice(_ERROR_PATHS)
        _logs.append({
            "timestamp": _now(),
            "level": "ERROR",
            "service": service,
            "method": "POST",
            "path": path,
            "status": 500,
            "latency_ms": random.randint(500, 3000),
            "message": f"Internal Server Error — unhandled exception in {service}",
            "stack_trace": f"RuntimeError: database connection timeout\n  at {service}/db.py:142",
        })
    return {
        "injected": count,
        "error_mode": True,
        "message": f"Injected {count} HTTP 500 errors. Log-Analyzer will detect them shortly.",
    }


@app.post("/admin/clear-errors")
def clear_errors() -> dict:
    """Clear error entries and restore healthy state."""
    global _error_mode  # noqa: PLW0603
    _error_mode = False
    _logs[:] = [e for e in _logs if e.get("status") != 500]
    _seed_healthy_logs()
    return {"error_mode": False, "message": "Errors cleared. Service restored to healthy state."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
