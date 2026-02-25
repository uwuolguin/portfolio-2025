#!/bin/bash
set -e

# =============================================================================
# Portfolio k3s Deployment Script - DigitalOcean 2GB Droplet
# Run as regular user with sudo privileges
# Deploys services SEQUENTIALLY to avoid OOM on 2GB RAM
# 
# UPDATED: Now loads Resend API key from .env.secrets
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
# Helper functions
# =============================================================================
wait_for_deployment_ready() {
    local name="$1"
    local namespace="$2"
    local timeout="${3:-180}"
    local description="${4:-$name}"

    log_info "Waiting for $description (max ${timeout}s)..."

    local counter=0
    local interval=5

    while [ $counter -lt $timeout ]; do
        local ready=$(kubectl get deployment "$name" -n "$namespace" \
            -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        local desired=$(kubectl get deployment "$name" -n "$namespace" \
            -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")

        # normalize empty to 0 (readyReplicas is absent when 0, not "0")
        ready="${ready:-0}"

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
    kubectl describe deployment "$name" -n "$namespace" 2>/dev/null | tail -20
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
wait_for_pods_ready() {
    local selector="$1"
    local namespace="$2"
    local timeout="${3:-120}"
    local description="${4:-$selector}"

    log_info "Waiting for $description (max ${timeout}s)..."

    local counter=0
    local interval=5

    while [ $counter -lt $timeout ]; do
        local ready=$(kubectl get pods -n "$namespace" -l "$selector" \
            -o jsonpath='{.items[*].status.containerStatuses[*].ready}' 2>/dev/null | tr ' ' '\n' | grep -c "true" || echo "0")
        local total=$(kubectl get pods -n "$namespace" -l "$selector" \
            --no-headers 2>/dev/null | wc -l | tr -d ' ')

        if [ "$total" -gt "0" ] && [ "$ready" = "$total" ]; then
            log_success "$description ready ($ready/$total)"
            return 0
        fi

        if [ $((counter % 20)) -eq 0 ]; then
            log_info "  $description: $ready/$total ready (${counter}/${timeout}s)"
        fi

        sleep $interval
        counter=$((counter + interval))
    done

    log_error "$description failed within ${timeout}s"
    kubectl describe pods -n "$namespace" -l "$selector" 2>/dev/null | tail -20
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
#   openssl rand -hex 16
#   → generates 16 raw random bytes (128 bits of entropy)
#   → encodes each byte as exactly 2 hex digits (0-9, a-f)
#   → output is ALWAYS exactly 32 characters, no filtering needed
#   → hex chars are safe in URLs, shell variables, YAML, and config parsers
#   → no tr, no head, no probabilistic failure — deterministic by design
#
#   If you want 64 chars: openssl rand -hex 32
#   If you want 128 bits of entropy in 32 chars: openssl rand -hex 16  ← used here
#
log_info "Generating secrets..."
POSTGRES_PASSWORD=$(openssl rand -hex 16)
JWT_SECRET=$(openssl rand -hex 16)
MINIO_PASSWORD=$(openssl rand -hex 16)

# =============================================================================
# Load Resend API key from .env.secrets
# =============================================================================
if [ -f "${SCRIPT_DIR}/.env.secrets" ]; then
    log_info "Loading Resend API key from .env.secrets"
    source "${SCRIPT_DIR}/.env.secrets"
    RESEND_KEY="${RESEND_API_KEY}"
    log_success "Resend API key loaded"
else
    log_error ".env.secrets not found!"
    log_error "Email verification will NOT work!"
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

# =============================================================================
# PostgreSQL Primary
# =============================================================================
log_info "Deploying PostgreSQL Primary..."
kubectl apply -f "$K8S_DIR/04-postgres-primary.yaml"

if ! wait_for_statefulset_ready "postgres-primary" "portfolio" 240 "PostgreSQL Primary"; then
    log_error "PostgreSQL Primary failed"
    kubectl logs -n portfolio postgres-primary-0 --tail=30 2>/dev/null || true
    exit 1
fi

sleep 5
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT pg_create_physical_replication_slot('replica_slot_1') WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = 'replica_slot_1');" \
  2>/dev/null || log_warn "Replication slot may already exist"

kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" 2>/dev/null || true

kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c "CREATE EXTENSION IF NOT EXISTS pg_cron;" 2>/dev/null || true

log_success "PostgreSQL Primary configured"
echo ""

# =============================================================================
# PostgreSQL Replica
# =============================================================================
log_info "Deploying PostgreSQL Replica..."
kubectl apply -f "$K8S_DIR/05-postgres-replica.yaml"

if ! wait_for_statefulset_ready "postgres-replica" "portfolio" 300 "PostgreSQL Replica"; then
    log_warn "Replica not ready - backend will use primary for reads"
    log_warn "Check: kubectl logs -n portfolio postgres-replica-0"
fi
echo ""

# =============================================================================
# Redis
# =============================================================================
log_info "Deploying Redis..."
kubectl apply -f "$K8S_DIR/06-redis.yaml"
if ! wait_for_pods_ready "app=redis" "portfolio" 60 "Redis"; then
    log_error "Redis failed"; exit 1
fi
echo ""

# =============================================================================
# MinIO
# =============================================================================
log_info "Deploying MinIO..."
kubectl apply -f "$K8S_DIR/07-minio.yaml"
if ! wait_for_pods_ready "app=minio" "portfolio" 90 "MinIO"; then
    log_error "MinIO failed"; exit 1
fi
echo ""

# =============================================================================
# Image Service
# =============================================================================
log_info "Deploying Image Service (1 replica, NSFW enabled - will use swap)..."
kubectl apply -f "$K8S_DIR/08-image-service.yaml"
if ! wait_for_pods_ready "app=image-service" "portfolio" 120 "Image Service"; then
    log_error "Image Service failed"; exit 1
fi
echo ""

# =============================================================================
# Backend
# =============================================================================
log_info "Deploying Backend (1 replica)..."
kubectl apply -f "$K8S_DIR/09-backend.yaml"
if ! wait_for_pods_ready "app=backend" "portfolio" 300 "Backend"; then
    log_error "Backend failed"
    kubectl logs -n portfolio -l app=backend --tail=30 2>/dev/null || true
    exit 1
fi
echo ""

# =============================================================================
# Nginx
# =============================================================================
log_info "Deploying Nginx..."
kubectl apply -f "$K8S_DIR/10-nginx.yaml"
if ! wait_for_pods_ready "app=nginx" "portfolio" 60 "Nginx"; then
    log_error "Nginx failed"; exit 1
fi
echo ""

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================"
echo "  DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""

log_info "All pods:"
kubectl get pods -n portfolio -o wide
echo ""

log_info "Services:"
kubectl get svc -n portfolio
echo ""

echo ""
echo "============================================"
echo "  ACCESS YOUR APP"
echo "============================================"
echo ""
echo "  Frontend: http://$DROPLET_IP/front-page/front-page.html"
echo "  API Docs: http://$DROPLET_IP/docs"
echo "  Health:   http://$DROPLET_IP/health"
echo ""
echo "============================================"
echo "  NEXT STEPS"
echo "============================================"
echo ""
echo "  1. Create admin user:"
echo "     kubectl exec -it -n portfolio deployment/backend -- \\"
echo "       python -m scripts.admin.create_admin"
echo ""
echo "  2. Seed test data (optional):"
echo "     kubectl exec -n portfolio deployment/backend -- \\"
echo "       python -m scripts.database.seed_test_data"
echo ""
echo "  3. Setup pg_cron:"
echo "     kubectl exec -n portfolio deployment/backend -- \\"
echo "       python -m scripts.database.manage_search_refresh_cron"
echo ""
echo "  4. Check replication:"
echo "     kubectl exec -n portfolio postgres-primary-0 -- \\"
echo "       psql -U postgres -d portfolio -c \\"
echo "       'SELECT client_addr, state FROM pg_stat_replication;'"
echo ""
echo "  5. Monitor memory:"
echo "     watch 'free -h && echo && kubectl top pods -n portfolio'"
echo ""
echo "  Credentials: ${SCRIPT_DIR}/.credentials"
echo ""
echo "============================================"
echo "  MEMORY BUDGET (2GB droplet + NSFW enabled)"
echo "============================================"
echo ""
echo "  k3s system:        ~300MB"
echo "  PostgreSQL primary: ~192-384MB"
echo "  PostgreSQL replica: ~128-256MB"
echo "  Redis:              ~32-96MB"
echo "  MinIO:              ~128-256MB"
echo "  Image Service:      ~384-768MB (TensorFlow NSFW)"
echo "  Backend:            ~192-512MB"
echo "  Nginx:              ~32-128MB"
echo "  Swap:               2GB (safety net)"
echo ""
echo "  Total requests:    ~1088MB"
echo "  Total limits:      ~2400MB (will use swap)"
echo "  Available:          2048MB + 2048MB swap"
echo "============================================"