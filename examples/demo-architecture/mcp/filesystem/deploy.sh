#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$SCRIPT_DIR/../../agent"

# Build custom image with supergateway and load into minikube
podman build -t localhost/mcp-filesystem-http:latest "$SCRIPT_DIR"
podman save localhost/mcp-filesystem-http:latest -o /tmp/mcp-filesystem-http.tar
minikube image load --overwrite /tmp/mcp-filesystem-http.tar
rm -f /tmp/mcp-filesystem-http.tar

# Install/upgrade the Helm chart (bjw-s/app-template)
if ! helm repo list | grep -q '^bjw-s\s'; then
  helm repo add bjw-s https://bjw-s-labs.github.io/helm-charts
  helm repo update bjw-s
fi

# Create/update ConfigMap with skills and TRI template mounted at /data/
kubectl create configmap demo-architecture-files \
  --from-file="$AGENT_DIR/skills/" \
  --dry-run=client -o yaml | kubectl apply -f -

helm upgrade --install filesystem-mcp bjw-s/app-template \
  -f "$SCRIPT_DIR/values.yaml"
