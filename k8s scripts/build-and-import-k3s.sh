#!/bin/bash
set -Eeuo pipefail

# =============================================================================
# Build and Import Images to k3s on DigitalOcean Droplet
# Run as regular user with:
#   - Docker group membership
#   - Passwordless sudo for k3s commands
#
# NO_CACHE flag:
#   NO_CACHE=true ./build-and-import-k3s.sh   → passes --pull --no-cache to every build
#   ./build-and-import-k3s.sh                 → uses Docker layer cache (faster)
#
# The GitHub Actions deploy workflow always sets NO_CACHE=true to guarantee
# no stale layer sneaks through between deploys.
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

# -----------------------------------------------------------------------------
# Verify passwordless sudo works
# -----------------------------------------------------------------------------
if ! sudo -n true 2>/dev/null; then
    log_error "Passwordless sudo is required."
    exit 1
fi

# -----------------------------------------------------------------------------
# Detect repo root
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Sanity check: readme.md is a reliable landmark for the repository root.
if [ ! -f "$REPO_ROOT/readme.md" ]; then
    log_error "Cannot find readme.md in repo root: $REPO_ROOT"
    exit 1
fi

cd "$REPO_ROOT"

# =============================================================================
# NO_CACHE flag
# =============================================================================
NO_CACHE_FLAG=""

if [ "${NO_CACHE:-false}" = "true" ]; then
    NO_CACHE_FLAG="--pull --no-cache"
    log_warn "NO_CACHE=true — all Docker layer cache will be ignored"
    log_warn "Build times will be significantly longer (10-20 min for image-service)"
fi

echo "=================================="
echo "Build & Import Images to k3s"
echo "=================================="
echo "Repo root: $(pwd)"

if [ -n "$NO_CACHE_FLAG" ]; then
    echo "Cache:     DISABLED (--pull --no-cache)"
else
    echo "Cache:     enabled"
fi

echo ""

# -----------------------------------------------------------------------------
# Verify Docker is available without sudo
# -----------------------------------------------------------------------------
if ! docker info >/dev/null 2>&1; then
    log_error "Docker is unavailable for the current user."
    log_error "Add deploy to the docker group and reconnect:"
    log_error "sudo usermod -aG docker deploy"
    exit 1
fi

# -----------------------------------------------------------------------------
# Check available RAM
# -----------------------------------------------------------------------------
FREE_MB=$(free -m | awk '/Mem:/ {print $7}')
log_info "Available RAM: ${FREE_MB}MB"

if [ "$FREE_MB" -lt 400 ]; then
    log_warn "Low RAM! Builds may be slow. Swap should help."
fi

echo ""

# =============================================================================
# Build images one at a time to reduce peak memory usage
# =============================================================================

# -----------------------------------------------------------------------------
# Backend
# -----------------------------------------------------------------------------
log_info "Building backend image..."
docker build $NO_CACHE_FLAG -t portfolio-backend:latest ./backend
log_success "Backend image built"
echo ""

log_info "Importing backend to k3s..."
docker save portfolio-backend:latest | sudo -n k3s ctr images import -
log_success "Backend imported"
echo ""

docker builder prune -f --filter "until=1m" 2>/dev/null || true

# -----------------------------------------------------------------------------
# Image service
# -----------------------------------------------------------------------------
log_info "Building image-service..."
docker build $NO_CACHE_FLAG -t portfolio-image-service:latest ./image-service
log_success "Image service built"
echo ""

log_info "Importing image-service to k3s..."
docker save portfolio-image-service:latest | sudo -n k3s ctr images import -
log_success "Image service imported"
echo ""

docker builder prune -f --filter "until=1m" 2>/dev/null || true

# -----------------------------------------------------------------------------
# PostgreSQL (custom image with pg_cron)
# -----------------------------------------------------------------------------
log_info "Building postgres image (pg_cron enabled)..."
docker build $NO_CACHE_FLAG -t portfolio-postgres:16 ./postgres
log_success "Postgres image built"
echo ""

log_info "Importing postgres to k3s..."
docker save portfolio-postgres:16 | sudo -n k3s ctr images import -
log_success "Postgres imported"
echo ""

docker builder prune -f --filter "until=1m" 2>/dev/null || true

# -----------------------------------------------------------------------------
# Nginx
# -----------------------------------------------------------------------------
log_info "Building nginx..."
docker build $NO_CACHE_FLAG -t portfolio-nginx:latest ./nginx
log_success "Nginx built"
echo ""

log_info "Importing nginx to k3s..."
docker save portfolio-nginx:latest | sudo -n k3s ctr images import -
log_success "Nginx imported"
echo ""

# =============================================================================
# Cleanup
# =============================================================================
log_info "Cleaning up Docker build cache..."

docker builder prune -af 2>/dev/null || true
docker image prune -f 2>/dev/null || true

log_success "Cleanup done"
echo ""

# =============================================================================
# Verify
# =============================================================================
echo "Imported images in k3s:"
sudo -n k3s ctr images ls | grep portfolio || true
echo ""

echo "=================================="
echo "All images built and imported!"
echo "=================================="
echo ""
echo "Next: ./deploy-k3s-local.sh"
echo ""