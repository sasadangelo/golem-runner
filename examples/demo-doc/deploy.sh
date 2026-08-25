#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the demo-doc Aria agent.
# Run from any directory:
#   examples/demo-doc/deploy.sh
#
# Prerequisites:
#   - Copy examples/demo-doc/.env.example → examples/demo-doc/.env and fill in values
#   - MCP server already deployed:
#       examples/demo-doc/mcp/llmwiki/deploy.sh
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLI_DIR="$(cd "$RUNNER_DIR/../golem-cli" && pwd)"
AGENT_ID="demo-doc-001"   # must match agent.id in agent/config.yaml

# ---------------------------------------------------------------------------
# Load secrets from .env
# ---------------------------------------------------------------------------

ENV_FILE="$SCRIPT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "==> No .env found — copying from .env.example (no secrets required for this demo)"
  cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
fi

set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
set +o allexport

# ---------------------------------------------------------------------------
# Create the agent namespace
# ---------------------------------------------------------------------------

kubectl create namespace "$AGENT_ID" --dry-run=client -o yaml | kubectl apply -f -
echo "==> Namespace '$AGENT_ID' ready"

# ---------------------------------------------------------------------------
# Deploy the agent via the Golem CLI
# ---------------------------------------------------------------------------

cd "$CLI_DIR"
golem agent create \
  --config    "$SCRIPT_DIR/agent/config.yaml" \
  --agents-md "$SCRIPT_DIR/agent/AGENTS.md"

echo ""
echo "✅ Agent '$AGENT_ID' deployed."
echo ""
echo "   Wait for the pod to be ready:"
echo "     golem agent status --id $AGENT_ID"
echo ""
echo "   Open a chat session:"
echo "     golem chat --id $AGENT_ID"
