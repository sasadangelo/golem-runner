#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

# ---------------------------------------------------------------------------
# Create the github-mcp-credentials Secret from .env
# ---------------------------------------------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ Missing $ENV_FILE — copy .env.example and fill in GITHUB_TOKEN"
  exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "❌ GITHUB_TOKEN is not set in $ENV_FILE"
  exit 1
fi

kubectl create secret generic github-mcp-credentials \
  --from-literal=GITHUB_TOKEN="$GITHUB_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -
echo "==> Secret 'github-mcp-credentials' ready"

# ---------------------------------------------------------------------------
# Install/upgrade the Helm chart
# ---------------------------------------------------------------------------
if ! helm repo list | grep -q '^bjw-s\s'; then
  helm repo add bjw-s https://bjw-s-labs.github.io/helm-charts
  helm repo update bjw-s
fi

helm upgrade --install github-mcp bjw-s/app-template -f "$SCRIPT_DIR/values.yaml"
