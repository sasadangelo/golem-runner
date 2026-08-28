#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the demo-a2a multi-agent setup.
#
# Deploys two agents in the right order:
#   1. report-writer-001  — must be registered in the CP before log-analyzer starts
#   2. log-analyzer-001   — will delegate to report-writer-001 at runtime
#
# Run from any directory:
#   examples/demo-a2a/deploy.sh
#
# Prerequisites:
#   - mock-log-service deployed: examples/demo-a2a/mock-log-service/deploy.sh
#   - golem CLI configured:      golem cp use --name local
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. Report Writer first — log-analyzer will delegate to it at task time
echo "==> Deploying report-writer-001..."
golem agent create \
  --config    "$SCRIPT_DIR/agent/report-writer/config.yaml" \
  --agents-md "$SCRIPT_DIR/agent/report-writer/AGENTS.md"

# 2. Log Analyzer
echo "==> Deploying log-analyzer-001..."
golem agent create \
  --config    "$SCRIPT_DIR/agent/log-analyzer/config.yaml" \
  --agents-md "$SCRIPT_DIR/agent/log-analyzer/AGENTS.md" \
  --skill     "$SCRIPT_DIR/agent/log-analyzer/skills/analyse-logs.md"

echo ""
echo "============================================================"
echo "  Multi-agent pipeline deployed!"
echo "  report-writer-001  — writes Markdown incident reports"
echo "  log-analyzer-001   — analyses logs, delegates to writer"
echo "============================================================"
echo ""
echo "Wait for pods to reach RUNNING:"
echo "  golem agent status --id report-writer-001"
echo "  golem agent status --id log-analyzer-001"
echo ""
echo "Inject errors into the mock log service:"
echo "  kubectl port-forward -n demo-a2a svc/mock-log-service 8080:8080 &"
echo "  curl -X POST http://localhost:8080/admin/inject-errors"
echo ""
echo "Trigger the full pipeline:"
echo "  golem agent task-send --agent log-analyzer-001 \\"
echo "    --message 'Analyse the application logs and produce an incident report.'"
echo ""
echo "Watch the delegation:"
echo "  golem agent tasks --agent log-analyzer-001"
echo "  golem agent tasks --agent report-writer-001"
