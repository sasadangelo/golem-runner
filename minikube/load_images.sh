#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
# Load the Golem Agent Runner image into the local Minikube cluster.
#
# Usage:
#   ./minikube/load_images.sh [TAG]
#
# Examples:
#   ./minikube/load_images.sh        # loads localhost/golem-runner:v1
#   ./minikube/load_images.sh v2     # loads localhost/golem-runner:v2
#
# Prerequisites:
#   - Minikube must be running  (minikube status)
#   - Image must be built first (./build_images.sh)
# -----------------------------------------------------------------------------

set -euo pipefail

TAG="${1:-v1}"
IMAGE="localhost/golem-runner:${TAG}"
ARCHIVE="/tmp/golem-runner-${TAG}.tar"

echo "==> Saving ${IMAGE} to ${ARCHIVE}"
podman save "${IMAGE}" -o "${ARCHIVE}"

echo "==> Loading ${ARCHIVE} into Minikube"
minikube image load "${ARCHIVE}"

echo "==> Cleaning up ${ARCHIVE}"
rm -f "${ARCHIVE}"

echo ""
echo "==> Done. Verifying:"
minikube image ls | grep golem-runner || echo "WARN: image not found in minikube image ls"
