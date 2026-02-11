#!/bin/bash
set -e

# =============================================================================
# Portfolio k3s Deployment Script - DigitalOcean 2GB Droplet
# Run as regular user with sudo privileges
# Deploys services SEQUENTIALLY to avoid OOM on 2GB RAM
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_DIR")" && pwd)"
K8S_DIR="$PROJECT_ROOT/k8s"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { printf '%b\n' "${BLUE}[INFO]${NC} $1"; }
log_success() { printf '%b\n' "${GREEN}[OK]${NC} $1"; }
log_warn()    { printf '%b\n' "${YELLOW}[WARN]${NC} $1"; }
log_error()   { printf '%b\n' "${RED}[ERROR]${NC} $1"; }

echo "============================================"
echo "Portfolio Deployment - DO 2GB Droplet"
echo "============================================"
echo ""
echo "K8s manifests: $K8S_DIR"
echo ""

# Check sudo
if ! sudo -v; then
    log_error "This script requires sudo privileges."
    exit 1
fi

# Show system resources
log_info "System resources:"
free -h | head -3
echo ""

# =============================================================================
# Ensure KUBECONFIG is set for non-root user
# =============================================================================
if [ ! -f "$HOME/.kube/config" ]; then
    log_info "Setting up kubectl for user $USER..."
    mkdir -p "$HOME/.kube"
    sudo cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
    sudo chown "$USER:$(id -gn)" "$HOME/.kube/config"
    chmod 600 "$HOME/.kube/config"
fi
export KUBECONFIG="$HOME/.kube/config"

# =============================================================================
# Helper functions (omitted for brevity - copy from original)
# =============================================================================
wait_for_pods_ready() {
    local label="$1"
    local namespace="$2"
    local timeout="${3:-180}"
    local description="${4:-pods}"
    log_info "Waiting for $description (max ${timeout}s)..."
    local counter=0
    local interval=5
    while [ $counter -lt $timeout ]; do
        local pod_count=$(kubectl get pods -l "$label" -n "$namespace" --no-headers 2>/dev/null | wc -l)
        if [ "$pod_count" -gt 0 ]; then
            if kubectl wait --for=condition=ready pod -l "$label" -n "$namespace" --timeout=10s &>/dev/null; then
                log_success "$description ready"
                return 0
            fi
        fi
        if [ $((counter % 20)) -eq 0 ]; then
            log_info "  Still waiting for $description... (${counter}/${timeout}s)"
        fi
        sleep $interval
        counter=$((counter + interval))
    done
    log_error "$description failed to start within ${timeout}s"
    kubectl get pods -l "$label" -n "$namespace" 2>/dev/null || true
    return 1
}

wait_for_statefulset_ready() {
    local name="$1"
    local namespace="$2"
    local timeout="${3:-240}"
    local description="${4:-$name}"
    log_info "Waiting for $description (max ${timeout}s)..."
    local counter=0
    local interval=5
    while [ $counter -lt $timeout ]; do
        local ready=$(kubectl get statefulset "$name" -n "$namespace" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        local desired=$(kubectl get statefulset "$name" -n "$namespace" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
        if [ "$ready" = "$desired" ] && [ "$ready" != "0" ]; then
            log_success "$description ready ($ready/$desired)"
            return 0
        fi
        if [ $((counter % 20)) -eq 0 ]; then
            log_info "  $description: $ready/$desired ready (${counter}/${timeout}s)"
        fi
        sleep $interval
        counter=$((counter + interval))
    done
    log_error "$description failed within ${timeout}s"
    kubectl describe statefulset "$name" -n "$namespace" 2>/dev/null | tail -20
    return 1
}

# =============================================================================
# Pre-checks
# =============================================================================
log_info "Checking prerequisites..."

if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot connect to k3s cluster."
    log_error "Make sure k3s is running: sudo systemctl status k3s"
    log_error "And kubeconfig exists: ls -la $HOME/.kube/config"
    exit 1
fi

# Verify images (k3s ctr needs sudo)
MISSING=0
for img in portfolio-backend:latest portfolio-image-service:latest portfolio-nginx:latest portfolio-postgres:16; do
    if ! sudo k3s ctr images ls | grep -q "$img"; then
        log_error "Missing image: $img"
        MISSING=1
    fi
done
if [ "$MISSING" -eq 1 ]; then
    log_error "Run build-and-import-k3s.sh first"
    exit 1
fi

log_success "All prerequisites OK"
echo ""

# =============================================================================
# Generate secrets
# =============================================================================
log_info "Generating secrets..."
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
JWT_SECRET=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
ADMIN_API_KEY=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
MINIO_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)

# Load Resend API key from .env.secrets if it exists
if [ -f "${SCRIPT_DIR}/.env.secrets" ]; then
    log_info "Loading Resend API key from .env.secrets"
    source "${SCRIPT_DIR}/.env.secrets"
    RESEND_KEY="${RESEND_API_KEY}"
    log_success "Resend API key loaded"
else
    log_error "⚠️  .env.secrets not found!"
    log_error "⚠️  Email verification will NOT work!"
    echo ""
    log_error "To fix this, run: ./set-resend-key.sh"
    echo ""
    read -p "Continue anyway with placeholder key? (yes/no): " continue_deploy
    if [ "$continue_deploy" != "yes" ] && [ "$continue_deploy" != "y" ]; then
        echo ""
        echo "Deployment aborted."
        echo ""
        echo "Run './set-resend-key.sh' to configure your Resend API key, then try again."
        exit 1
    fi
    RESEND_KEY="re_YOUR_KEY_HERE_EMAILS_WILL_NOT_WORK"
    log_warn "Continuing with placeholder Resend key - email features disabled"
fi
echo ""

# Detect droplet public IP (fail if not detected)
DROPLET_IP=$(
  curl -s --max-time 2 http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address 2>/dev/null ||
  curl -s --max-time 2 ifconfig.me 2>/dev/null
)

if [[ -z "$DROPLET_IP" ]]; then
  log_error "Failed to detect droplet public IP via metadata or external service"
  exit 1
fi

log_info "Detected droplet IP: $DROPLET_IP"

# =============================================================================
# Deploy step by step (kubectl uses user's kubeconfig, no sudo needed)
# =============================================================================

# Namespace
log_info "Creating namespace..."
kubectl apply -f "$K8S_DIR/00-namespace.yaml"
echo ""

# ConfigMap
log_info "Creating ConfigMap..."
kubectl apply -f "$K8S_DIR/01-configmap.yaml"
echo ""

# Patch ALLOWED_ORIGINS with droplet IP
kubectl patch configmap portfolio-config -n portfolio --type merge \
  -p "{\"data\":{\"ALLOWED_ORIGINS\":\"[\\\"http://localhost\\\",\\\"http://localhost:80\\\",\\\"http://${DROPLET_IP}\\\"]\"}}"

log_info "Patched ALLOWED_ORIGINS with droplet IP: ${DROPLET_IP}"

# Secrets
log_info "Creating secrets..."
kubectl create secret generic portfolio-secrets \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@postgres-primary:5432/portfolio?sslmode=require" \
  --from-literal=DATABASE_URL_PRIMARY="postgresql://postgres:${POSTGRES_PASSWORD}@postgres-primary:5432/portfolio?sslmode=require" \
  --from-literal=DATABASE_URL_REPLICA="postgresql://postgres:${POSTGRES_PASSWORD}@postgres-replica:5432/portfolio?sslmode=require" \
  --from-literal=ALEMBIC_DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@postgres-primary:5432/portfolio?sslmode=require" \
  --from-literal=REDIS_URL="redis://redis:6379/0" \
  --from-literal=MINIO_ROOT_USER=minioadmin \
  --from-literal=MINIO_ROOT_PASSWORD="$MINIO_PASSWORD" \
  --from-literal=SECRET_KEY="$JWT_SECRET" \
  --from-literal=ADMIN_API_KEY="$ADMIN_API_KEY" \
  --from-literal=ADMIN_BYPASS_IPS='["10.0.0.0/8","172.16.0.0/12","192.168.0.0/16"]' \
  --from-literal=RESEND_API_KEY="$RESEND_KEY" \
  --from-literal=ADMIN_EMAIL="admin@example.com" \
  --from-literal=API_BASE_URL="http://$DROPLET_IP" \
  -n portfolio \
  --dry-run=client -o yaml | kubectl apply -f -

# Save credentials
cat > "${SCRIPT_DIR}/.credentials" <<EOF
# Generated credentials - $(date -Iseconds)
# KEEP THIS FILE SECURE
DROPLET_IP=$DROPLET_IP
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
JWT_SECRET=$JWT_SECRET
ADMIN_API_KEY=$ADMIN_API_KEY
MINIO_PASSWORD=$MINIO_PASSWORD
RESEND_API_KEY=$RESEND_KEY
DATABASE_URL_PRIMARY=postgresql://postgres:${POSTGRES_PASSWORD}@postgres-primary:5432/portfolio?sslmode=require
DATABASE_URL_REPLICA=postgresql://postgres:${POSTGRES_PASSWORD}@postgres-replica:5432/portfolio?sslmode=require
EOF
chmod 600 "${SCRIPT_DIR}/.credentials"
log_success "Secrets created (saved to .credentials)"
echo ""

# PVCs
log_info "Creating PVCs..."
kubectl apply -f "$K8S_DIR/03-pvcs.yaml"
echo ""

echo ""
echo "============================================"
echo "  DEPLOYMENT COMPLETE!"
echo "============================================"