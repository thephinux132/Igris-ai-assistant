#!/bin/bash
# Build and tag Igris Docker image

set -e

VERSION="2.0.0"
IMAGE_NAME="igris"

echo "Building Igris Docker image..."

# Build image
docker build \
    -t "${IMAGE_NAME}:${VERSION}" \
    -t "${IMAGE_NAME}:latest" \
    -f Dockerfile \
    .

echo ""
echo "Build complete!"
echo "  ${IMAGE_NAME}:${VERSION}"
echo "  ${IMAGE_NAME}:latest"
echo ""
echo "Run with:"
echo "  docker run -p 8420:8420 ${IMAGE_NAME}:${VERSION}"
echo ""
echo "Or use docker-compose:"
echo "  docker-compose up -d"
