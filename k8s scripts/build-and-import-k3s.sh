#!/bin/bash
set -e

echo "Building images locally..."
docker build -t portfolio-postgres:latest ../postgres
docker build -t portfolio-backend:latest ../backend
docker build -t portfolio-image-service:latest ../image-service
docker build -t portfolio-nginx:latest ../nginx

echo "Importing images to k3s..."
docker save portfolio-postgres:latest | sudo k3s ctr images import -
docker save portfolio-backend:latest | sudo k3s ctr images import -
docker save portfolio-image-service:latest | sudo k3s ctr images import -
docker save portfolio-nginx:latest | sudo k3s ctr images import -

echo "✅ All images imported to k3s"
sudo k3s ctr images ls | grep portfolio