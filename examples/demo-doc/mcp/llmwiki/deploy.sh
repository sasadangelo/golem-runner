#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the llmwiki stack into minikube (local mode, no auth, demo-only).
#
# Deploys three components:
#   llmwiki     — single pod with mcp (8080) + api (8000) containers,
#                 emptyDir workspace shared between them
#   llmwiki-web — stateless Next.js UI (3000)
#
# Run from any directory:
#   examples/demo-doc/mcp/llmwiki/deploy.sh
#
# Prerequisites:
#   - minikube running           (minikube start)
#   - /Users/sasadangelo/github.com/lucasastorian/llmwiki cloned
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LLMWIKI_ROOT="/Users/sasadangelo/github.com/lucasastorian/llmwiki"

# ---- Sanity checks ----------------------------------------------------------
if [[ ! -d "$LLMWIKI_ROOT/mcp" ]]; then
  echo "ERROR: llmwiki not found at $LLMWIKI_ROOT" >&2
  echo "  Clone it: git clone https://github.com/lucasastorian/llmwiki.git $LLMWIKI_ROOT" >&2
  exit 1
fi
command -v minikube &>/dev/null || { echo "ERROR: minikube not found." >&2; exit 1; }

# ---- Helper -----------------------------------------------------------------
_build_load() {
  # _build_load <image-name> <build-context-tmpdir> [--build-arg KEY=VAL ...]
  local name="$1"; shift
  local ctx="$1";  shift
  echo "==> [$name] Building"
  podman build "$@" -t "localhost/$name:latest" "$ctx"
  echo "==> [$name] Loading into minikube"
  podman save "localhost/$name:latest" -o "/tmp/$name.tar"
  minikube image load --overwrite "/tmp/$name.tar"
  rm -f "/tmp/$name.tar"
}

# ---- Helm repo --------------------------------------------------------------
if ! helm repo list 2>/dev/null | grep -q '^bjw-s\s'; then
  helm repo add bjw-s https://bjw-s-labs.github.io/helm-charts && helm repo update bjw-s
fi

# ---- 1. MCP image -----------------------------------------------------------
MCP_DIR="$(mktemp -d)"; trap "rm -rf '$MCP_DIR'" EXIT
cp -r "$LLMWIKI_ROOT/mcp/." "$MCP_DIR/"
cp "$SCRIPT_DIR/http_server.py"  "$MCP_DIR/http_server.py"
cp "$SCRIPT_DIR/Dockerfile"      "$MCP_DIR/Dockerfile"
[[ -d "$LLMWIKI_ROOT/shared" ]] && cp -r "$LLMWIKI_ROOT/shared" "$MCP_DIR/shared"
_build_load "llmwiki-mcp" "$MCP_DIR"

# ---- 2. API image -----------------------------------------------------------
API_DIR="$(mktemp -d)"; trap "rm -rf '$API_DIR'" EXIT
cp -r "$LLMWIKI_ROOT/api/." "$API_DIR/"
cp "$SCRIPT_DIR/Dockerfile.api" "$API_DIR/Dockerfile"
[[ -d "$LLMWIKI_ROOT/shared" ]] && cp -r "$LLMWIKI_ROOT/shared" "$API_DIR/shared"
# Include the llmwiki CLI so the initContainer can run `llmwiki init /workspace`
[[ -f "$LLMWIKI_ROOT/llmwiki" ]] && cp "$LLMWIKI_ROOT/llmwiki" "$API_DIR/llmwiki"
_build_load "llmwiki-api" "$API_DIR"

# ---- 3. Deploy mcp+api pod --------------------------------------------------
echo "==> Deploying llmwiki (mcp+api) Helm release"
helm upgrade --install llmwiki bjw-s/app-template -f "$SCRIPT_DIR/values.yaml"

# ---- 4. Web UI image --------------------------------------------------------
# NEXT_PUBLIC_* vars are baked at build time.
# They use localhost because the browser accesses the API via port-forward.
API_EXT="${LLMWIKI_API_EXTERNAL_URL:-http://localhost:8000}"
MCP_EXT="${LLMWIKI_MCP_EXTERNAL_URL:-http://localhost:8080/mcp}"

WEB_DIR="$(mktemp -d)"; trap "rm -rf '$WEB_DIR'" EXIT
cp -r "$LLMWIKI_ROOT/web/." "$WEB_DIR/"
cp "$SCRIPT_DIR/web/Dockerfile" "$WEB_DIR/Dockerfile"
_build_load "llmwiki-web" "$WEB_DIR" \
  --build-arg "NEXT_PUBLIC_API_URL=$API_EXT" \
  --build-arg "NEXT_PUBLIC_MCP_URL=$MCP_EXT"

# ---- 5. Deploy web ----------------------------------------------------------
echo "==> Deploying llmwiki-web Helm release"
helm upgrade --install llmwiki-web bjw-s/app-template -f "$SCRIPT_DIR/web/values.yaml"

# ---- Done -------------------------------------------------------------------
echo ""
echo "✅ llmwiki stack deployed."
echo ""
echo "   Wait for pods:"
echo "     kubectl rollout status deployment/llmwiki"
echo "     kubectl rollout status deployment/llmwiki-web"
echo ""
echo "   Expose services (3 separate terminals):"
echo "     kubectl port-forward svc/llmwiki-mcp 8080:8080"
echo "     kubectl port-forward svc/llmwiki-api 8000:8000"
echo "     kubectl port-forward svc/llmwiki-web 3000:3000"
echo ""
echo "   Open UI: open http://localhost:3000"
