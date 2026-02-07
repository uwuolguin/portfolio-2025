#!/bin/bash
set -e

# =============================================================================
# k3s Installation Script with Proper Health Checks
# =============================================================================
# Installs k3s with explicit cluster naming and robust readiness checks
# =============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
  printf '%b\n' "${BLUE}[INFO]${NC} $1"
}

log_success() {
  printf '%b\n' "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
  printf '%b\n' "${YELLOW}[WARN]${NC} $1"
}

log_error() {
  printf '%b\n' "${RED}[ERROR]${NC} $1"
}

# =============================================================================
# Configuration
# =============================================================================
CLUSTER_NAME="portfolio-k3s"
KUBECONFIG_PATH="$HOME/.kube/config"

echo "=================================="
echo "k3s Installation Script"
echo "=================================="
echo ""
echo "Cluster Name: $CLUSTER_NAME"
echo "Kubeconfig: $KUBECONFIG_PATH"
echo ""

# =============================================================================
# Check Prerequisites
# =============================================================================
log_info "Checking prerequisites..."

if [ "$EUID" -eq 0 ]; then 
    log_error "Do not run this script as root (sudo will be used when needed)"
    exit 1
fi

if ! command -v curl &> /dev/null; then
    log_error "curl not found - please install curl first"
    exit 1
fi

log_success "Prerequisites OK"
echo ""

# =============================================================================
# Check Existing Installation
# =============================================================================
log_info "Checking for existing k3s installation..."

if command -v k3s &> /dev/null; then
    log_success "k3s is already installed"
    k3s --version
    echo ""

    # Ensure k3s service is running
    if sudo systemctl is-active --quiet k3s; then
        log_success "k3s service is running"
    else
        log_warn "k3s is installed but not running"
        log_info "Starting k3s service..."

        if sudo systemctl start --wait k3s; then
            log_success "k3s service started"
        else
            log_error "k3s service failed to start"
            sudo systemctl status k3s --no-pager
            exit 1
        fi
    fi
else
    # =============================================================================
    # Install k3s
    # =============================================================================
    log_info "Installing k3s..."
    echo ""

    log_info "Running installation..."
    curl -sfL https://get.k3s.io | sh -s - --write-kubeconfig-mode 644

    log_success "k3s installed"
    echo ""
fi

# =============================================================================
# Verify Installation
# =============================================================================
log_info "Verifying installation..."
echo ""

# Show cluster info
echo "Cluster Information:"
kubectl cluster-info | head -n 2
echo ""

# Show node status
echo "Node Status:"
kubectl get nodes -o wide
echo ""

# Show system pods
echo "System Pods:"
kubectl get pods -n kube-system
echo ""

# Show storage class
echo "Storage Classes:"
kubectl get storageclass
echo ""

# =============================================================================
# Installation Summary
# =============================================================================
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "✅ k3s cluster: $CLUSTER_NAME"
echo "✅ Kubeconfig: $KUBECONFIG_PATH"
echo "✅ API server: https://127.0.0.1:6443"
echo "✅ Default storage: local-path"
echo ""

log_success "k3s is ready for deployment!"
echo ""

echo "=================================="
echo "Next Steps"
echo "=================================="
echo ""
echo "1. Build and import custom images:"
echo "   ./build-and-import-k3s.sh"
echo ""
echo "2. Deploy the application:"
echo "   ./deploy-k8s-local.sh"
echo ""
echo "=================================="
echo "Useful Commands"
echo "=================================="
echo ""
echo "# View cluster info"
echo "kubectl cluster-info"
echo ""
echo "# View all pods"
echo "kubectl get pods -A"
echo ""
echo "# View logs (if issues occur)"
echo "sudo journalctl -u k3s -f"
echo ""
echo "# Stop k3s"
echo "sudo systemctl stop k3s"
echo ""
echo "# Uninstall k3s completely"
echo "/usr/local/bin/k3s-uninstall.sh"
echo ""
echo "=================================="