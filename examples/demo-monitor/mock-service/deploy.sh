#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Deploy the demo-monitor mock service on Kubernetes (minikube).
# Run from any directory:
#   examples/demo-monitor/mock-service/deploy.sh
#
# The mock service is a simple FastAPI app that exposes:
#   GET  /health       — returns 200 OK when healthy, 503 when down
#   POST /admin/down   — puts the service into the DOWN state
#   POST /admin/up     — restores the service to the UP state
#
# Prerequisites:
#   - minikube running  (minikube start)
#   - kubectl configured to target minikube
#   - podman or docker available for building images
# -----------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="localhost/demo-monitor/mock-service:latest"
NAMESPACE="demo-monitor"

# ---------------------------------------------------------------------------
# Build image and load into minikube
# ---------------------------------------------------------------------------

echo "==> Building mock-service image..."
podman build -t "$IMAGE" "$SCRIPT_DIR"
podman save "$IMAGE" -o /tmp/mock-service.tar
minikube image load --overwrite /tmp/mock-service.tar
rm -f /tmp/mock-service.tar
echo "==> Image loaded into minikube"

# ---------------------------------------------------------------------------
# Create namespace
# ---------------------------------------------------------------------------

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
echo "==> Namespace '$NAMESPACE' ready"

# ---------------------------------------------------------------------------
# Deploy Deployment + Service
# ---------------------------------------------------------------------------

kubectl apply -f - << YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mock-service
  namespace: $NAMESPACE
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mock-service
  template:
    metadata:
      labels:
        app: mock-service
    spec:
      containers:
        - name: mock-service
          image: $IMAGE
          imagePullPolicy: Never
          ports:
            - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: mock-service
  namespace: $NAMESPACE
spec:
  selector:
    app: mock-service
  ports:
    - port: 8080
      targetPort: 8080
  type: ClusterIP
YAML

echo "==> mock-service deployed in namespace '$NAMESPACE'"
echo ""
echo "Service is reachable inside the cluster at:"
echo "  http://mock-service.$NAMESPACE.svc.cluster.local:8080/health"
echo ""
echo "To reach it from your machine:"
echo "  kubectl port-forward -n $NAMESPACE svc/mock-service 8080:8080"
echo ""
echo "Then test with:"
echo "  curl http://localhost:8080/health"
echo "  curl -X POST http://localhost:8080/admin/down"
echo "  curl -X POST http://localhost:8080/admin/up"
