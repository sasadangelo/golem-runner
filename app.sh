#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# app.sh — Start the Golem Agent Runner (development mode)
# Usage: ./app.sh [--port PORT] [--host HOST] [--no-reload]
# -----------------------------------------------------------------------------
set -euo pipefail

HOST="0.0.0.0"
PORT="8001"
RELOAD="--reload"

# Parse optional flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)      HOST="$2";  shift 2 ;;
    --port)      PORT="$2";  shift 2 ;;
    --no-reload) RELOAD="";  shift   ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# Locate the repo root (directory containing this script)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$REPO_ROOT/src/golem-runner"
ENV_FILE="$APP_DIR/.env"

# Load .env if present
if [[ -f "$ENV_FILE" ]]; then
  echo "Loading environment from $ENV_FILE"
  set -o allexport
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +o allexport
else
  echo "WARNING: $ENV_FILE not found — WATSONX_API_KEY must be set in the environment."
fi

# Require WATSONX_API_KEY
if [[ -z "${WATSONX_API_KEY:-}" ]]; then
  echo "ERROR: WATSONX_API_KEY is not set. Create $ENV_FILE or export the variable."
  exit 1
fi

echo "Starting Golem Agent Runner on http://$HOST:$PORT ..."
exec uv run \
  --directory "$REPO_ROOT" \
  uvicorn main:app \
  --app-dir "$APP_DIR" \
  --host "$HOST" \
  --port "$PORT" \
  $RELOAD
