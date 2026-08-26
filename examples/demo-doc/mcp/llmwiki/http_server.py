"""HTTP wrapper for the llmwiki local MCP server.

Exposes the same MCP tools as local_server.py but over HTTP/SSE via
FastMCP's streamable-HTTP transport so that golem-runner agents can
reach it over the Kubernetes cluster network.

Usage (inside the container):
    python http_server.py --workspace /workspace

The workspace directory is expected to be writable persistent storage.
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import uvicorn
from starlette.responses import PlainTextResponse
from starlette.routing import Route

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("llmwiki.http")

# Single fixed user identity for the local singleton workspace.
_LOCAL_USER_ID: str = os.environ.get("LLMWIKI_USER_ID", str(uuid.uuid5(uuid.NAMESPACE_DNS, "local")))
os.environ["SUPAVAULT_USER_ID"] = _LOCAL_USER_ID


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM Wiki HTTP MCP server (local mode)")
    parser.add_argument(
        "--workspace",
        default=os.environ.get("WORKSPACE_PATH", "/workspace"),
        help="Path to workspace folder (default: /workspace or $WORKSPACE_PATH)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)), help="Port (default: 8080)")
    return parser.parse_args()


async def _init_workspace(workspace_path: str) -> None:
    """Mirror local_server.py: create dirs, SQLite, default workspace row."""
    ws = Path(workspace_path).resolve()

    (ws / "wiki").mkdir(parents=True, exist_ok=True)
    (ws / ".llmwiki").mkdir(parents=True, exist_ok=True)
    (ws / ".llmwiki" / "cache").mkdir(parents=True, exist_ok=True)

    from vaultfs import SqliteVaultFS  # type: ignore[import-not-found]

    await SqliteVaultFS.init(str(ws))

    fs = SqliteVaultFS(_LOCAL_USER_ID)
    existing = await fs.get_workspace()
    if not existing:
        ws_name = ws.name
        ws_id = await fs.ensure_workspace(ws_name)
        from datetime import date

        today = date.today().isoformat()
        overview_content = (
            "---\n"
            "title: Overview\n"
            f"description: Research hub for {ws_name}.\n"
            f"date: {today}\n"
            "tags: [overview, wiki]\n"
            "---\n\n"
            f"This wiki tracks research on {ws_name}.\n\n"
            "## Key Findings\n\n"
            "No sources ingested yet."
        )
        await fs.create_document(
            ws_id,
            "overview.md",
            "Overview",
            "/wiki/",
            "md",
            overview_content,
            ["overview", "wiki"],
            date=today,
            metadata={"description": f"Research hub for {ws_name}."},
        )
        overview_file = ws / "wiki" / "overview.md"
        if not overview_file.exists():
            overview_file.write_text(overview_content + "\n", encoding="utf-8")
        logger.info("Initialized workspace: %s", ws)
    else:
        logger.info("Workspace ready: %s", ws)


def _build_app(_workspace_path: str) -> Any:
    """Build the FastMCP streamable-HTTP ASGI app (no auth, local mode)."""
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings
    from tools import register  # type: ignore[import-not-found]
    from vaultfs import SqliteVaultFS  # type: ignore[import-not-found]

    mcp = FastMCP(
        name="LLM Wiki",
        instructions=(
            "You are connected to an LLM Wiki workspace. The user has uploaded files, notes, "
            "and documents that you can read, search, edit, and organize. "
            "Call the `guide` tool first to see available knowledge bases and learn the full workflow."
        ),
        # No auth in local mode — connections come only from inside the cluster.
        # Allow in-cluster DNS hostnames so the MCP SDK's DNS-rebinding protection
        # does not reject requests with 421 Misdirected Request.
        transport_security=TransportSecuritySettings(
            allowed_hosts=[
                "llmwiki-mcp.default.svc.cluster.local:8080",
                "llmwiki-mcp.default.svc.cluster.local",
                "localhost:8080",
                "localhost",
                "127.0.0.1:8080",
                "127.0.0.1",
            ]
        ),
    )

    def _get_user_id(_ctx: Any) -> str:
        return _LOCAL_USER_ID

    register(mcp, _get_user_id, lambda user_id: SqliteVaultFS(user_id))

    @mcp.tool(name="ping", description="Test connectivity")
    async def ping() -> str:
        return "pong"

    async def health(_request: Any) -> PlainTextResponse:
        return PlainTextResponse("OK")

    app = mcp.streamable_http_app()
    app.router.routes.insert(0, Route("/health", health))
    return app


def main() -> None:
    args = _parse_args()
    workspace = str(Path(args.workspace).resolve())

    # Make the mcp/ directory importable regardless of working directory.
    mcp_src = Path(__file__).parent
    if str(mcp_src) not in sys.path:
        sys.path.insert(0, str(mcp_src))

    # Shared directory for the SQLite schema (llmwiki/shared/sqlite_schema.sql).
    shared_dir = mcp_src.parent / "shared"
    if shared_dir.is_dir() and str(shared_dir) not in sys.path:
        sys.path.insert(0, str(shared_dir))

    # Initialise workspace synchronously before serving.
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_init_workspace(workspace))

    app = _build_app(workspace)

    logger.info(
        "LLM Wiki MCP server ready — workspace: %s  http://%s:%d/mcp",
        workspace,
        args.host,
        args.port,
    )
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
