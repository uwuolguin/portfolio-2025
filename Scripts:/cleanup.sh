#!/bin/bash

# Cleanup script for k3s deployment
# WARNING: This will delete all data!

echo "=================================="
echo "Portfolio k3s Cleanup Script"
echo "=================================="
echo ""
echo "This will delete:"
echo "  - All pods, services, deployments"
echo "  - All persistent data (PostgreSQL, Redis, MinIO)"
echo "  - Namespace and all resources"
echo ""

read -p "Are you sure? Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Deleting namespace and all resources..."
kubectl delete namespace portfolio --wait=true

echo ""
echo "Cleanup complete!"
echo ""
echo "To redeploy, run:"
echo "  ./deploy.sh [registry-prefix]"
echo ""