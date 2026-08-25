#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if ! helm repo list | grep -q '^bjw-s\s'; then
  helm repo add bjw-s https://bjw-s-labs.github.io/helm-charts
  helm repo update bjw-s
fi

helm upgrade --install github-mcp bjw-s/app-template -f "$SCRIPT_DIR/values.yaml"
