#!/bin/bash
set -e

# =============================================================================
# Portfolio k3s Deployment Script (Local Images)
# =============================================================================
# Prerequisites: Run ./build-and-import-k3s.sh first
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="${SCRIPT_DIR}/k8s"

echo "=================================="
echo "Portfolio k3s Deployment Script"
echo "=================================="
echo ""
echo "Using locally imported images"
echo "K8s manifests: $K8S_DIR"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check prerequisites
log_info "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    log_error "kubectl not found"
    exit 1
fi

if ! command -v openssl &> /dev/null; then
    log_error "openssl not found"
    exit 1
fi

# Check k3s connectivity
if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot connect to Kubernetes cluster"
    exit 1
fi

# Verify images are imported
log_info "Verifying images are imported to k3s..."
MISSING_IMAGES=()
for img in portfolio-backend:latest portfolio-image-service:latest portfolio-nginx:latest; do
    if ! sudo k3s ctr images ls | grep -q "$img"; then
        MISSING_IMAGES+=("$img")
    fi
done

if [ ${#MISSING_IMAGES[@]} -gt 0 ]; then
    log_error "Missing images in k3s:"
    for img in "${MISSING_IMAGES[@]}"; do
        echo "  - $img"
    done
    echo ""
    log_error "Run './build-and-import-k3s.sh' first to import images"
    exit 1
fi

log_success "All required images found in k3s"
echo ""

# Generate secure secrets
log_info "Generating secure secrets..."
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
JWT_SECRET=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
ADMIN_API_KEY=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
MINIO_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
log_success "Secrets generated"
echo ""

# Create namespace
log_info "Creating namespace..."
kubectl apply -f "$K8S_DIR/00-namespace.yaml"
echo ""

# Create ConfigMap
log_info "Creating ConfigMap..."
kubectl apply -f "$K8S_DIR/01-configmap.yaml"
echo ""

# Create secrets (programmatically for security)
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
  --from-literal=ADMIN_BYPASS_IPS="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16" \
  --from-literal=RESEND_API_KEY="re_YOUR_KEY_HERE" \
  --from-literal=ADMIN_EMAIL="admin@example.com" \
  --from-literal=API_BASE_URL="http://localhost" \
  -n portfolio \
  --dry-run=client -o yaml | kubectl apply -f -

# Save credentials locally
cat > "${SCRIPT_DIR}/.credentials" <<EOF
# Generated credentials - KEEP SECURE!
# Generated at: $(date -Iseconds)
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
JWT_SECRET=$JWT_SECRET
ADMIN_API_KEY=$ADMIN_API_KEY
MINIO_PASSWORD=$MINIO_PASSWORD

# Database URLs
DATABASE_URL_PRIMARY=postgresql://postgres:${POSTGRES_PASSWORD}@postgres-primary:5432/portfolio?sslmode=require
DATABASE_URL_REPLICA=postgresql://postgres:${POSTGRES_PASSWORD}@postgres-replica:5432/portfolio?sslmode=require
EOF
chmod 600 "${SCRIPT_DIR}/.credentials"
log_success "Secrets created and saved to .credentials"
log_warn "Keep .credentials file secure!"
echo ""

# Create PVCs
log_info "Creating Persistent Volume Claims..."
kubectl apply -f "$K8S_DIR/03-pvcs.yaml"
echo ""

# Deploy PostgreSQL Primary
log_info "Deploying PostgreSQL Primary..."
kubectl apply -f "$K8S_DIR/04-postgres-primary.yaml"

log_info "Waiting for PostgreSQL Primary to be ready (max 3 minutes)..."
if ! kubectl wait --for=condition=ready pod -l app=postgres-primary -n portfolio --timeout=180s; then
    log_error "PostgreSQL Primary failed to start"
    kubectl logs -n portfolio -l app=postgres-primary --tail=50
    exit 1
fi
log_success "PostgreSQL Primary is ready"
echo ""

# Create replication slot on primary
log_info "Creating replication slot on primary..."
sleep 5  # Give postgres a moment to fully initialize

kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT pg_create_physical_replication_slot('replica_slot_1') WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = 'replica_slot_1');" \
  2>/dev/null || log_warn "Replication slot may already exist"

# Create extensions
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" \
  2>/dev/null || true

kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c "CREATE EXTENSION IF NOT EXISTS pg_cron;" \
  2>/dev/null || true

log_success "Replication slot and extensions configured"
echo ""

# Deploy PostgreSQL Replica
log_info "Deploying PostgreSQL Replica..."
kubectl apply -f "$K8S_DIR/05-postgres-replica.yaml"

log_info "Waiting for PostgreSQL Replica to be ready (max 5 minutes)..."
if ! kubectl wait --for=condition=ready pod -l app=postgres-replica -n portfolio --timeout=300s; then
    log_warn "PostgreSQL Replica not ready yet - this is OK, backend will fall back to primary"
    log_info "You can check replica status later with:"
    echo "  kubectl logs -n portfolio -l app=postgres-replica"
else
    log_success "PostgreSQL Replica is ready"
fi
echo ""

# Verify replication
log_info "Verifying replication status..."
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c "SELECT client_addr, state, sync_state FROM pg_stat_replication;" \
  2>/dev/null || log_warn "Could not verify replication - replica may still be initializing"
echo ""

# Deploy Redis
log_info "Deploying Redis..."
kubectl apply -f "$K8S_DIR/06-redis.yaml"
kubectl wait --for=condition=ready pod -l app=redis -n portfolio --timeout=60s
log_success "Redis is ready"
echo ""

# Deploy MinIO
log_info "Deploying MinIO..."
kubectl apply -f "$K8S_DIR/07-minio.yaml"
kubectl wait --for=condition=ready pod -l app=minio -n portfolio --timeout=60s
log_success "MinIO is ready"
echo ""

# Deploy Image Service (2 replicas)
log_info "Deploying Image Service (2 replicas)..."
kubectl apply -f "$K8S_DIR/08-image-service.yaml"
kubectl wait --for=condition=ready pod -l app=image-service -n portfolio --timeout=120s
log_success "Image Service is ready"
echo ""

# Deploy Backend (2 replicas)
log_info "Deploying Backend (2 replicas with read/write splitting)..."
kubectl apply -f "$K8S_DIR/09-backend.yaml"
kubectl wait --for=condition=ready pod -l app=backend -n portfolio --timeout=180s
log_success "Backend is ready"
echo ""

# Deploy Nginx
log_info "Deploying Nginx..."
kubectl apply -f "$K8S_DIR/10-nginx.yaml"
kubectl wait --for=condition=ready pod -l app=nginx -n portfolio --timeout=60s
log_success "Nginx is ready"
echo ""

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "=================================="
echo "Deployment Complete!"
echo "=================================="
echo ""

log_info "All services:"
kubectl get pods -n portfolio -o wide
echo ""

log_info "Services:"
kubectl get svc -n portfolio
echo ""

# Get LoadBalancer IP
LOADBALANCER_IP=$(kubectl get svc nginx -n portfolio -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending...")

echo ""
echo "=================================="
echo "Access Information"
echo "=================================="
echo ""
echo "Application URL: http://$LOADBALANCER_IP"
echo ""
echo "Credentials saved to: ${SCRIPT_DIR}/.credentials"
echo ""
echo "=================================="
echo "Next Steps"
echo "=================================="
echo ""
echo "1. Create admin user:"
echo "   kubectl exec -n portfolio deployment/backend -- python -m scripts.admin.create_admin"
echo ""
echo "2. Seed test data (optional):"
echo "   kubectl exec -n portfolio deployment/backend -- python -m scripts.database.seed_test_data"
echo ""
echo "3. Check replication status:"
echo "   kubectl exec -n portfolio postgres-primary-0 -- psql -U postgres -c 'SELECT * FROM pg_stat_replication;'"
echo ""
echo "4. Check replica is in recovery mode:"
echo "   kubectl exec -n portfolio postgres-replica-0 -- psql -U postgres -c 'SELECT pg_is_in_recovery();'"
echo ""
echo "5. View logs:"
echo "   kubectl logs -n portfolio deployment/backend -f"
echo "   kubectl logs -n portfolio deployment/image-service -f"
echo ""
echo "=================================="