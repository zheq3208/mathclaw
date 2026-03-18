#!/usr/bin/env bash
set -euo pipefail

IMAGE_NAME=${1:-mathclaw:latest}

docker build -f deploy/Dockerfile -t "$IMAGE_NAME" .

echo "Built image: $IMAGE_NAME"
