#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the demo-chatbot Tony agent.
# Run from any directory:
#   examples/demo-chatbot/deploy.sh
#
# Prerequisites:
#   - golem CLI installed and a control plane registered:
#       golem cp add --name local --url http://localhost:9000
#       golem cp use --name local
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLI_DIR="$(cd "$RUNNER_DIR/../golem-cli" && pwd)"
AGENT_ID="demo-chatbot-001"   # must match agent.id in agent/config.yaml

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
