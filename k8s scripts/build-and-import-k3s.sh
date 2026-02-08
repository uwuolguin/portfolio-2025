#!/bin/bash
set -e

# =============================================================================
# Build and Import Images to k3s on DigitalOcean Droplet
# Run as regular user with sudo privileges
# =============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { printf '%b\n' "${BLUE}[INFO]${NC} $1"; }
log_success() { printf '%b\n' "${GREEN}[OK]${NC} $1"; }
log_warn()    { printf '%b\n' "${YELLOW}[WARN]${NC} $1"; }
log_error()   { printf '%b\n' "${RED}[ERROR]${NC} $1"; }

# Check sudo
if ! sudo -v; then
    log_error "This script requires sudo privileges."
    exit 1
fi

# Detect repo root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$REPO_ROOT/docker-compose.yml" ]; then
    cd "$REPO_ROOT"
elif [ -f "$(dirname "$REPO_ROOT")/docker-compose.yml" ]; then
    cd "$(dirname "$REPO_ROOT")"
else
    echo "ERROR: Cannot find docker-compose.yml. Run from repo root."
    exit 1
fi

echo "=================================="
echo "Build & Import Images to k3s"
echo "=================================="
echo "Repo root: $(pwd)"
echo ""

# Determine if docker needs sudo
DOCKER_CMD="docker"
if ! docker info &>/dev/null 2>&1; then
    log_warn "docker requires sudo (run 'newgrp docker' to avoid this)"
    DOCKER_CMD="sudo docker"
fi

# Check available RAM
FREE_MB=$(free -m | awk '/Mem:/ {print $7}')
log_info "Available RAM: ${FREE_MB}MB"

if [ "$FREE_MB" -lt 400 ]; then
    log_warn "Low RAM! Builds may be slow. Swap should help."
fi
echo ""

# =============================================================================
# Build images one at a time to reduce peak memory usage
# =============================================================================

log_info "Building backend image..."
$DOCKER_CMD build -t portfolio-backend:latest ./backend
log_success "Backend image built"
echo ""

# Import immediately and clean up to free memory
log_info "Importing backend to k3s..."
$DOCKER_CMD save portfolio-backend:latest | sudo k3s ctr images import -
log_success "Backend imported"
echo ""

$DOCKER_CMD builder prune -f --filter "until=1m" 2>/dev/null || true

log_info "Building image-service..."
$DOCKER_CMD build -t portfolio-image-service:latest ./image-service
log_success "Image service built"
echo ""

log_info "Importing image-service to k3s..."
$DOCKER_CMD save portfolio-image-service:latest | sudo k3s ctr images import -
log_success "Image service imported"
echo ""

$DOCKER_CMD builder prune -f --filter "until=1m" 2>/dev/null || true

log_info "Building nginx..."
$DOCKER_CMD build -t portfolio-nginx:latest ./nginx
log_success "Nginx built"
echo ""

log_info "Importing nginx to k3s..."
$DOCKER_CMD save portfolio-nginx:latest | sudo k3s ctr images import -
log_success "Nginx imported"
echo ""

# =============================================================================
# Cleanup
# =============================================================================
log_info "Cleaning up Docker build cache..."
$DOCKER_CMD builder prune -af 2>/dev/null || true
$DOCKER_CMD image prune -f 2>/dev/null || true
log_success "Cleanup done"
echo ""

# =============================================================================
# Verify
# =============================================================================
echo "Imported images in k3s:"
sudo k3s ctr images ls | grep portfolio
echo ""

echo "=================================="
echo "All images built and imported!"
echo "=================================="
echo ""
echo "Next: ./deploy-k3s-droplet.sh"
echo ""
