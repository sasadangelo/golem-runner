#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the demo-architecture Sage agent.
# Run from any directory:
#   examples/demo-architecture/deploy.sh
#
# Prerequisites:
#   - Copy examples/demo-architecture/mcp/github/.env.example → .env and fill in values
#   - MCP servers already deployed:
#       examples/demo-architecture/mcp/filesystem/deploy.sh
#       examples/demo-architecture/mcp/github/deploy.sh
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLI_DIR="$(cd "$RUNNER_DIR/../golem-cli" && pwd)"
AGENT_ID="demo-architecture-001"   # must match agent.id in agent/config.yaml
ENV_FILE="$SCRIPT_DIR/mcp/github/.env"

# ---------------------------------------------------------------------------
# Create github-mcp-credentials Secret in the agent namespace.
# The runner pod needs GITHUB_TOKEN to forward it as an Authorization header
# to the GitHub MCP server (resolved via env_secrets in config.yaml).
# ---------------------------------------------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ Missing $ENV_FILE — copy mcp/github/.env.example and fill in GITHUB_TOKEN"
  exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "❌ GITHUB_TOKEN is not set in $ENV_FILE"
  exit 1
fi

kubectl create namespace "$AGENT_ID" --dry-run=client -o yaml | kubectl apply -f -
kubectl create secret generic github-mcp-credentials \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --namespace "$AGENT_ID" \
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

echo ""
echo "✅ Agent '$AGENT_ID' deployed."
echo ""
echo "   Wait for the pod to be ready:"
echo "     golem agent status --id $AGENT_ID"
echo ""
echo "   Open a chat session:"
echo "     golem chat --id $AGENT_ID"
