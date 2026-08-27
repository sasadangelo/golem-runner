#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the demo-monitor Matteo agent.
# Run from any directory:
#   examples/demo-monitor/deploy.sh
#
# Prerequisites:
#   1. Copy .env.example → .env and fill in SLACK_WEBHOOK_URL
#   2. Deploy the mock service first:
#        examples/demo-monitor/mock-service/deploy.sh
#   3. golem CLI installed and a control plane registered:
#        golem cp add --name local --url http://localhost:9000
#        golem cp use --name local
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_ID="demo-monitor-001"   # must match agent.id in agent/config.yaml
NAMESPACE="$AGENT_ID"

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

: "${SLACK_WEBHOOK_URL:?SLACK_WEBHOOK_URL must be set in $ENV_FILE}"

# ---------------------------------------------------------------------------
# Create the agent namespace and inject SLACK_WEBHOOK_URL as a K8s Secret.
# The runner pod reads it as an environment variable via envFrom.
# ---------------------------------------------------------------------------

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
echo "==> Namespace '$NAMESPACE' ready"

kubectl create secret generic slack-credentials \
  --from-literal=SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL" \
  --namespace="$NAMESPACE" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "==> Secret 'slack-credentials' ready in namespace '$NAMESPACE'"

# ---------------------------------------------------------------------------
# Deploy the agent via the Golem CLI
# ---------------------------------------------------------------------------

golem agent create \
  --config    "$SCRIPT_DIR/agent/config.yaml" \
  --agents-md "$SCRIPT_DIR/agent/AGENTS.md"

echo ""
echo "==> Matteo agent deployed (id: $AGENT_ID)"
echo ""
echo "The agent will check mock-service health every 30 seconds."
echo "Watch tasks accumulate:"
echo "  golem agent tasks --agent $AGENT_ID"
echo ""
echo "Bring the mock service DOWN to trigger a Slack alert:"
echo "  kubectl port-forward -n demo-monitor svc/mock-service 8080:8080 &"
echo "  curl -X POST http://localhost:8080/admin/down"
echo ""
echo "Bring it back UP to see the recovery notification:"
echo "  curl -X POST http://localhost:8080/admin/up"
