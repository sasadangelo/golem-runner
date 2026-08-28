#!/usr/bin/env bash
# Deploy the mock-log-service into minikube.
# Run from any directory: examples/demo-a2a/mock-log-service/deploy.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="localhost/demo-a2a/mock-log-service:latest"
NAMESPACE="demo-a2a"

echo "==> Building mock-log-service image..."
podman build -t "$IMAGE" "$SCRIPT_DIR"
podman save "$IMAGE" -o /tmp/mock-log-service.tar
minikube image load --overwrite /tmp/mock-log-service.tar
rm -f /tmp/mock-log-service.tar
echo "==> Image loaded into minikube"

kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -

kubectl apply -f - << YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mock-log-service
  namespace: $NAMESPACE
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mock-log-service
  template:
    metadata:
      labels:
        app: mock-log-service
    spec:
      containers:
        - name: mock-log-service
          image: $IMAGE
          imagePullPolicy: Never
          ports:
            - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: mock-log-service
  namespace: $NAMESPACE
spec:
  selector:
    app: mock-log-service
  ports:
    - port: 8080
      targetPort: 8080
  type: ClusterIP
YAML

echo ""
echo "==> mock-log-service deployed in namespace '$NAMESPACE'"
echo "    http://mock-log-service.$NAMESPACE.svc.cluster.local:8080/logs"
echo ""
echo "To reach it from your machine:"
echo "  kubectl port-forward -n $NAMESPACE svc/mock-log-service 8080:8080"
echo "  curl http://localhost:8080/logs"
echo "  curl -X POST http://localhost:8080/admin/inject-errors"
