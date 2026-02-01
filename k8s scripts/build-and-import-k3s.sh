#!/bin/bash
set -e

echo "Building images locally..."

# Backend and services need custom builds
docker build -t portfolio-backend:latest ../backend
docker build -t portfolio-image-service:latest ../image-service
docker build -t portfolio-nginx:latest ../nginx

echo "Importing images to k3s..."
docker save portfolio-backend:latest | sudo k3s ctr images import -
docker save portfolio-image-service:latest | sudo k3s ctr images import -
docker save portfolio-nginx:latest | sudo k3s ctr images import -

echo "✅ All images imported to k3s"
echo ""
echo "Note: PostgreSQL, Redis, and MinIO use official images (pulled automatically)"
echo ""
sudo k3s ctr images ls | grep portfolio