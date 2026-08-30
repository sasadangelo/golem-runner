#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Copyright (c) 2026 Salvatore D'Angelo, Code4Projects
# Licensed under the MIT License. See LICENSE.md for details.
# -----------------------------------------------------------------------------
# Delete the Golem Agent Runner image locally from Podman or Docker.
#
# Usage:
#   ./delete_images.sh [TAG]
#
# Examples:
#   ./delete_images.sh        # deletes localhost/golem-runner:v1
#   ./delete_images.sh v2     # deletes localhost/golem-runner:v2
# -----------------------------------------------------------------------------

set -euo pipefail

TAG="${1:-v0.0.1}"
IMAGE="localhost/golem-runner:${TAG}"

echo "==> Deleting local Podman/Docker image: ${IMAGE}"
podman rmi "${IMAGE}" 2>/dev/null || docker rmi "${IMAGE}" 2>/dev/null || echo "Local image ${IMAGE} not found or could not be deleted."

echo ""
echo "==> Done."
