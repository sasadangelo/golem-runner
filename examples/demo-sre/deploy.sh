#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the demo-sre Fabio agent.
# Run from any directory:
#   examples/demo-sre/deploy.sh
#
# Prerequisites:
#   - MCP servers already deployed:
#       examples/demo-sre/mcp/kubernetes/deploy.sh
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CLI_DIR="$(cd "$RUNNER_DIR/../golem-cli" && pwd)"

cd "$CLI_DIR"
golem agent create \
  --config    "$SCRIPT_DIR/agent/config.yaml" \
  --agents-md "$SCRIPT_DIR/agent/AGENTS.md" \
  --skill     "$SCRIPT_DIR/agent/skills/check-health.md" \
  --skill     "$SCRIPT_DIR/agent/skills/inspect-env.md" \
  --skill     "$SCRIPT_DIR/agent/skills/inspect-k8s.md"
