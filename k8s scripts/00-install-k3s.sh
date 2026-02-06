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
K3S_VERSION="${K3S_VERSION:-}"  # Empty = latest, or set to specific version
KUBECONFIG_PATH="$HOME/.kube/config"
MAX_WAIT_TIME=120  # Maximum seconds to wait for k3s to be ready

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
    
    # Check if k3s service is running
    if sudo systemctl is-active --quiet k3s; then
        log_success "k3s service is running"
    else
        log_warn "k3s is installed but not running"
        log_info "Starting k3s service..."
        sudo systemctl start k3s
        
        # Wait for service to be active
        log_info "Waiting for k3s service to start..."
        COUNTER=0
        while [ $COUNTER -lt 30 ]; do
            if sudo systemctl is-active --quiet k3s; then
                log_success "k3s service started"
                break
            fi
            sleep 1
            COUNTER=$((COUNTER + 1))
        done
        
        if [ $COUNTER -ge 30 ]; then
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
    
    # Build installation command with options
    INSTALL_CMD="curl -sfL https://get.k3s.io | sh -s - "
    
    # Add version if specified
    if [ -n "$K3S_VERSION" ]; then
        INSTALL_CMD="INSTALL_K3S_VERSION=$K3S_VERSION $INSTALL_CMD"
        log_info "Installing k3s version: $K3S_VERSION"
    else
        log_info "Installing latest k3s version"
    fi
    
    # Add k3s options
    # --cluster-init: Enable embedded etcd (for future multi-node support)
    # --write-kubeconfig-mode: Make kubeconfig readable by all users
    INSTALL_CMD="$INSTALL_CMD --write-kubeconfig-mode 644"
    
    log_info "Running installation..."
    eval "$INSTALL_CMD"
    
    log_success "k3s installed"
    echo ""
fi

# =============================================================================
# Wait for k3s to be Ready (Proper Health Check)
# =============================================================================
log_info "Waiting for k3s to be ready (max ${MAX_WAIT_TIME}s)..."

# Function to check if k3s is fully ready
check_k3s_ready() {
    # Check 1: Service is running
    if ! sudo systemctl is-active --quiet k3s; then
        return 1
    fi
    
    # Check 2: API server is responsive
    if ! sudo k3s kubectl get --raw /healthz &>/dev/null; then
        return 1
    fi
    
    # Check 3: Node is Ready
    if ! sudo k3s kubectl get nodes 2>/dev/null | grep -q " Ready"; then
        return 1
    fi
    
    # Check 4: Core pods are running
    local core_pods=$(sudo k3s kubectl get pods -n kube-system --no-headers 2>/dev/null | wc -l)
    if [ "$core_pods" -lt 3 ]; then
        return 1
    fi
    
    return 0
}

# Wait loop with timeout
COUNTER=0
WAIT_INTERVAL=2
while [ $COUNTER -lt $MAX_WAIT_TIME ]; do
    if check_k3s_ready; then
        log_success "k3s is ready!"
        break
    fi
    
    # Show progress every 10 seconds
    if [ $((COUNTER % 10)) -eq 0 ]; then
        log_info "Still waiting... (${COUNTER}/${MAX_WAIT_TIME}s)"
    fi
    
    sleep $WAIT_INTERVAL
    COUNTER=$((COUNTER + WAIT_INTERVAL))
done

if [ $COUNTER -ge $MAX_WAIT_TIME ]; then
    log_error "k3s failed to become ready within ${MAX_WAIT_TIME} seconds"
    echo ""
    log_info "Checking k3s status..."
    sudo systemctl status k3s --no-pager || true
    echo ""
    log_info "Checking k3s logs..."
    sudo journalctl -u k3s -n 50 --no-pager || true
    exit 1
fi

echo ""

# =============================================================================
# Set Up Kubeconfig with Cluster Name
# =============================================================================
log_info "Setting up kubectl configuration..."

# Create .kube directory if it doesn't exist
mkdir -p "$(dirname "$KUBECONFIG_PATH")"

# Copy k3s kubeconfig
sudo cp /etc/rancher/k3s/k3s.yaml "$KUBECONFIG_PATH"
sudo chown "$(id -u):$(id -g)" "$KUBECONFIG_PATH"
chmod 600 "$KUBECONFIG_PATH"

# Update cluster name in kubeconfig
# This changes 'default' to your custom cluster name
sed -i.bak "s/name: default$/name: $CLUSTER_NAME/" "$KUBECONFIG_PATH"
sed -i.bak "s/cluster: default$/cluster: $CLUSTER_NAME/" "$KUBECONFIG_PATH"
sed -i.bak "s/current-context: default$/current-context: $CLUSTER_NAME/" "$KUBECONFIG_PATH"

# Set the kubeconfig environment variable
export KUBECONFIG="$KUBECONFIG_PATH"

# Add to shell profile for persistence
if [ -f "$HOME/.bashrc" ]; then
    if ! grep -q "KUBECONFIG=$KUBECONFIG_PATH" "$HOME/.bashrc"; then
        echo "" >> "$HOME/.bashrc"
        echo "# k3s kubeconfig" >> "$HOME/.bashrc"
        echo "export KUBECONFIG=$KUBECONFIG_PATH" >> "$HOME/.bashrc"
    fi
fi

if [ -f "$HOME/.zshrc" ]; then
    if ! grep -q "KUBECONFIG=$KUBECONFIG_PATH" "$HOME/.zshrc"; then
        echo "" >> "$HOME/.zshrc"
        echo "# k3s kubeconfig" >> "$HOME/.zshrc"
        echo "export KUBECONFIG=$KUBECONFIG_PATH" >> "$HOME/.zshrc"
    fi
fi

log_success "Kubeconfig configured at: $KUBECONFIG_PATH"
log_info "Cluster name set to: $CLUSTER_NAME"
echo ""

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