# Dockerfile for the llmwiki MCP server running in LOCAL mode.
#
# Built from the upstream mcp/ directory of the llmwiki project:
#   /Users/sasadangelo/github.com/lucasastorian/llmwiki/mcp
#
# The image is self-contained: it copies the mcp/ source tree and the
# shared/ SQLite schema.  The workspace is mounted as a persistent volume
# at /workspace by the Helm chart so state survives pod restarts.

FROM python:3.11-slim-bookworm

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PORT=8080 MODE=local

# Install uv for fast dependency installation
RUN pip install --no-cache-dir uv

# Copy lock file first so Docker layer cache is reused when code changes
COPY requirements.lock .
RUN uv pip install --system --require-hashes -r requirements.lock

# Copy the mcp source tree and the shared SQLite schema.
# The mcp/ source tree is staged in the build context root, and the shared/
# folder is copied alongside it (by deploy.sh).
COPY . .

# sqlite.py resolves the schema as Path(__file__).parent.parent.parent / "shared"
# i.e.  /app/vaultfs/sqlite.py → /app/vaultfs → /app → / → /shared/sqlite_schema.sql
# Symlink /shared → /app/shared so the schema is found at both paths.
RUN ln -sf /app/shared /shared

# Workspace directory (mounted at runtime via PVC / emptyDir)
RUN mkdir -p /workspace

# The local server exposes an HTTP/SSE MCP endpoint served by uvicorn.
# We reuse local_server.py's startup logic but wrap it in a tiny HTTP shim
# so that golem-runner can reach it over the cluster network.
# local_server.py already accepts --workspace; we forward /workspace.
EXPOSE 8080
CMD ["python", "http_server.py", "--workspace", "/workspace"]
