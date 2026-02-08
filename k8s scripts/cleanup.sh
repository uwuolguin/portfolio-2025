#!/bin/bash

echo "=================================="
echo "Portfolio k3s Cleanup"
echo "=================================="
echo ""
echo "This will DELETE all data!"
echo ""

read -p "Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

# Ensure kubeconfig
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

echo ""
echo "Deleting namespace..."
kubectl delete namespace portfolio --wait=true --timeout=120s || true

echo ""
echo "Cleanup complete!"
echo ""
echo "To redeploy: ./deploy-k3s-droplet.sh"
