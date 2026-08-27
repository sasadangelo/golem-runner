# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
"""Mock service for the demo-monitor example.

Exposes three endpoints:
  GET  /health       — returns 200 OK when healthy, 503 when down
  POST /admin/down   — puts the service into the DOWN state
  POST /admin/up     — restores the service to the UP state
"""

import uvicorn
from fastapi import FastAPI, HTTPException

app: FastAPI = FastAPI(title="Mock Service", version="1.0.0")

_healthy: bool = True


@app.get(path="/health")
def health() -> dict[str, str]:
    """Return service health status."""
    if _healthy:
        return {"status": "ok", "service": "mock-service"}
    raise HTTPException(status_code=503, detail="Service unavailable — manually triggered DOWN state.")


@app.post(path="/admin/down")
def go_down() -> dict[str, str]:
    """Put the service into the DOWN state."""
    global _healthy  # noqa: PLW0603
    _healthy = False
    return {"status": "DOWN", "message": "Service is now down. Monitor agent will detect this shortly."}


@app.post(path="/admin/up")
def go_up() -> dict[str, str]:
    """Restore the service to the UP state."""
    global _healthy  # noqa: PLW0603
    _healthy = True
    return {"status": "UP", "message": "Service is back up. Monitor agent will detect recovery shortly."}


@app.get(path="/")
def root() -> dict[str, str]:
    return {"service": "mock-service", "state": "healthy" if _healthy else "down"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
