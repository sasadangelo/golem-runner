#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the demo-architecture Sage agent.
# Run from any directory:
#   examples/demo-architecture/deploy.sh
#
# Prerequisites:
#   - Copy examples/demo-architecture/.env.example → examples/demo-architecture/.env and fill in values
#   - MCP servers already deployed:
#       examples/demo-architecture/mcp/filesystem/deploy.sh
#       examples/demo-architecture/mcp/github/deploy.sh
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLI_DIR="$(cd "$RUNNER_DIR/../golem-cli" && pwd)"
AGENT_ID="demo-architecture-001"   # must match agent.id in agent/config.yaml

# ---------------------------------------------------------------------------
# Load secrets from .env
# ---------------------------------------------------------------------------

ENV_FILE="$SCRIPT_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Copy .env.example → .env and fill in the values." >&2
  exit 1
fi

set -o allexport
# shellcheck disable=SC1090
source "$ENV_FILE"
set +o allexport

: "${GITHUB_TOKEN:?GITHUB_TOKEN must be set in $ENV_FILE}"

# ---------------------------------------------------------------------------
# Create the agent namespace and secret before the Control Plane deploys the pod.
# The namespace name equals agent.id so the CP can create the pod in it directly.
# ---------------------------------------------------------------------------

kubectl create namespace "$AGENT_ID" --dry-run=client -o yaml | kubectl apply -f -
echo "==> Namespace '$AGENT_ID' ready"

kubectl create secret generic github-mcp-credentials \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --namespace="$AGENT_ID" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "==> Secret 'github-mcp-credentials' ready in namespace '$AGENT_ID'"

# ---------------------------------------------------------------------------
# Deploy the agent via the Golem CLI
# ---------------------------------------------------------------------------

cd "$CLI_DIR"
golem agent create \
  --config    "$SCRIPT_DIR/agent/config.yaml" \
  --agents-md "$SCRIPT_DIR/agent/AGENTS.md" \
  --skill     "$SCRIPT_DIR/agent/skills/interview.md" \
  --skill     "$SCRIPT_DIR/agent/skills/generate-tri.md" \
  --skill     "$SCRIPT_DIR/agent/skills/tri-template.md"
