SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/../.."

helm upgrade -i -n kubernetes-mcp-server --create-namespace kubernetes-mcp-server oci://ghcr.io/containers/charts/kubernetes-mcp-server -f "$DEMO_DIR/mcp/kubernetes/values.yaml"

kubectl rollout status -n kubernetes-mcp-server deployment/kubernetes-mcp-server
