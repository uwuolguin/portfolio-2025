#!/bin/bash
set -e

# =============================================================================
# k3s Installation for DigitalOcean Droplet (2GB RAM)
# Run as regular user with sudo privileges
# =============================================================================

# NOTE:
# The following commands make system changes persistent across reboots
# (e.g. /etc/fstab, /etc/sysctl.conf). Persistence is powerful, but dangerous:
# if this script is executed multiple times without guards, it may append
# duplicate or conflicting entries, leading to boot warnings, undefined
# behavior, or hard-to-debug system states.
#
# Examples:
#   - Repeatedly appending swap entries to /etc/fstab
#   - Duplicating kernel parameters in /etc/sysctl.conf
#
# For this reason, persistence-related commands must be written to be
# idempotent (safe to run multiple times), or explicitly checked before
# modification.

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { printf '%b\n' "${BLUE}[INFO]${NC} $1"; }
log_success() { printf '%b\n' "${GREEN}[OK]${NC} $1"; }
log_warn()    { printf '%b\n' "${YELLOW}[WARN]${NC} $1"; }
log_error()   { printf '%b\n' "${RED}[ERROR]${NC} $1"; }

echo "=================================="
echo "k3s Install - DigitalOcean Droplet"
echo "=================================="
echo ""

# Check sudo access
if ! sudo -v; then
    log_error "This script requires sudo privileges."
    exit 1
fi

# =============================================================================
# Step 0: Add swap (critical for 2GB RAM)
# =============================================================================
log_info "Checking swap..."
if [ "$(swapon --show | wc -l)" -eq 0 ]; then
    log_warn "No swap detected. Creating 2GB swap file..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab > /dev/null
    sudo sysctl vm.swappiness=10
    echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf > /dev/null
    log_success "2GB swap created and enabled"
else
    log_success "Swap already configured"
fi

free -h
echo ""

# =============================================================================
# Step 1: Prerequisites
# =============================================================================
log_info "Installing prerequisites..."
sudo apt-get update -qq
sudo apt-get install -y -qq curl openssl git > /dev/null 2>&1
log_success "Prerequisites installed"
echo ""

# =============================================================================
# Step 2: Install Docker (needed to build images)
# =============================================================================
# -----------------------------------------------------------------------------
# Docker Installation Note
# -----------------------------------------------------------------------------
# The block below downloads the official Docker install script from get.docker.com
# and saves it to install-docker.sh WITHOUT executing it.
#
# Before running this script in a production environment, inspect it first:
#   less install-docker.sh        # scroll with arrows, search with /, quit with q
#
# Once you have reviewed the script and are satisfied, run it manually:
#   sh install-docker.sh
#
# For automated/demo environments the script is executed directly after download.
# For production, consider installing Docker via apt instead:
#   https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository
# -----------------------------------------------------------------------------
if ! command -v docker &> /dev/null; then
    log_info "Installing Docker..."
    curl -fsSL https://get.docker.com -o install-docker.sh
    # Show the script so you can review it
    less install-docker.sh
    # Pause and wait for user confirmation
    read -p "Press Enter to continue with Docker installation, or Ctrl+C to cancel..."
    sh install-docker.sh
    sudo systemctl enable docker
    sudo systemctl start docker
    sudo usermod -aG docker "$USER"  
    log_success "Docker installed"
    log_warn "You were added to the 'docker' group."
    log_warn "Run 'newgrp docker' or log out/in for it to take effect."
    log_warn "Until then, docker commands will need sudo."
else
    log_success "Docker already installed"
fi
echo ""

# =============================================================================
# Step 3: Install k3s (lightweight Kubernetes)
# =============================================================================
# -----------------------------------------------------------------------------
# k3s Installation Note
# -----------------------------------------------------------------------------
# The block below downloads the official k3s install script from get.k3s.io
# and saves it to install-k3s.sh WITHOUT executing it.
#
# Before proceeding, inspect it first:
#   less install-k3s.sh           # scroll with arrows, search with /, quit with q
#
# Once you have reviewed the script and are satisfied, press Enter to continue.
# If you are not satisfied, press Ctrl+C to cancel the installation entirely.
#
# For production, consider pinning to a specific k3s version instead:
#   https://docs.k3s.io/installation/configuration
# -----------------------------------------------------------------------------
if command -v k3s &> /dev/null; then
    log_success "k3s already installed"
    k3s --version

    if ! sudo systemctl is-active --quiet k3s; then
        log_info "Starting k3s service..."
        sudo systemctl start k3s
    fi
else
    log_info "Installing k3s..."

    curl -sfL https://get.k3s.io -o install-k3s.sh

    less install-k3s.sh

    read -r -p "Press Enter to continue with k3s installation, or Ctrl+C to cancel..."

    sudo INSTALL_K3S_EXEC="\
--write-kubeconfig-mode 644 \
--disable traefik \
--kubelet-arg=eviction-hard=memory.available<100Mi \
--kubelet-arg=eviction-soft=memory.available<200Mi \
--kubelet-arg=eviction-soft-grace-period=memory.available=30s" \
    sh install-k3s.sh

    sudo systemctl is-active --quiet k3s || {
        log_error "k3s failed to start"
        exit 1
    }

    log_success "k3s installed"
fi

# Setup kubectl access for current user (no sudo needed for kubectl after this)
log_info "Configuring kubectl for user $USER..."
mkdir -p "$HOME/.kube"
sudo cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
sudo chown "$USER:$(id -gn)" "$HOME/.kube/config"
chmod 600 "$HOME/.kube/config"
export KUBECONFIG="$HOME/.kube/config"

if ! grep -q 'KUBECONFIG' "$HOME/.bashrc" 2>/dev/null; then
    echo 'export KUBECONFIG="$HOME/.kube/config"' >> "$HOME/.bashrc"
fi

log_success "kubectl configured for user $USER (no sudo needed)"

# Wait for k3s to be ready
log_info "Waiting for k3s to be ready..."
COUNTER=0
while [ $COUNTER -lt 60 ]; do
    if kubectl get nodes &>/dev/null; then
        break
    fi
    sleep 2
    COUNTER=$((COUNTER + 1))
done

echo ""
kubectl get nodes -o wide
echo ""

# =============================================================================
# Summary
# =============================================================================
echo "=================================="
echo "Installation Complete!"
echo "=================================="
echo ""
echo "System resources:"
free -h
echo ""
df -h /
echo ""
echo "IMPORTANT: If this is the first docker install, run:"
echo "  newgrp docker"
echo "or log out and back in so docker works without sudo."
echo ""
echo "Next steps:"
echo "  1. Build images:     ./build-and-import-k3s.sh"
echo "  2. Deploy:           ./deploy-k3s-local.sh"
echo "=================================="
