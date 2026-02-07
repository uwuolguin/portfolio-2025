#!/bin/bash
set -e

# =============================================================================
# Portfolio k3s Deployment Script (Local Images)
# =============================================================================
# Prerequisites: 
#   1. Run ./00-install-k3s.sh first
#   2. Run ./build-and-import-k3s.sh to import images
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K8S_DIR="$(dirname "$SCRIPT_DIR")/k8s"

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
# Helper: Wait for pod readiness with timeout
# =============================================================================
wait_for_pods_ready() {
    local label="$1"
    local namespace="$2"
    local timeout="${3:-180}"  # Default 3 minutes
    local description="${4:-pods}"
    
    log_info "Waiting for $description to be ready (max ${timeout}s)..."
    
    local counter=0
    local interval=5
    
    while [ $counter -lt $timeout ]; do
        # Check if any pods exist with this label
        local pod_count=$(kubectl get pods -l "$label" -n "$namespace" --no-headers 2>/dev/null | wc -l)
        
        if [ "$pod_count" -eq 0 ]; then
            if [ $((counter % 15)) -eq 0 ]; then
                log_info "Waiting for pods to be created... (${counter}/${timeout}s)"
            fi
        else
            # Check if all pods are ready
            local ready_count=$(kubectl get pods -l "$label" -n "$namespace" --no-headers 2>/dev/null | grep -c "Running" || echo "0")
            
            if [ "$ready_count" -eq "$pod_count" ]; then
                # Additional check: verify readiness condition
                if kubectl wait --for=condition=ready pod -l "$label" -n "$namespace" --timeout=10s &>/dev/null; then
                    log_success "$description ready ($ready_count/$pod_count pods)"
                    return 0
                fi
            fi
            
            if [ $((counter % 15)) -eq 0 ]; then
                log_info "$description not ready yet: $ready_count/$pod_count pods running (${counter}/${timeout}s)"
            fi
        fi
        
        sleep $interval
        counter=$((counter + interval))
    done
    
    log_error "$description failed to become ready within ${timeout}s"
    return 1
}

# =============================================================================
# Helper: Wait for StatefulSet to be ready
# =============================================================================
wait_for_statefulset_ready() {
    local name="$1"
    local namespace="$2"
    local timeout="${3:-180}"
    local description="${4:-$name}"
    
    log_info "Waiting for StatefulSet $description to be ready (max ${timeout}s)..."
    
    local counter=0
    local interval=5
    
    while [ $counter -lt $timeout ]; do
        # Get current and desired replicas
        local current=$(kubectl get statefulset "$name" -n "$namespace" -o jsonpath='{.status.currentReplicas}' 2>/dev/null || echo "0")
        local ready=$(kubectl get statefulset "$name" -n "$namespace" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
        local desired=$(kubectl get statefulset "$name" -n "$namespace" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
        
        if [ "$ready" = "$desired" ] && [ "$current" = "$desired" ]; then
            log_success "StatefulSet $description ready ($ready/$desired replicas)"
            return 0
        fi
        
        if [ $((counter % 15)) -eq 0 ]; then
            log_info "StatefulSet $description: $ready/$desired replicas ready (${counter}/${timeout}s)"
        fi
        
        sleep $interval
        counter=$((counter + interval))
    done
    
    log_error "StatefulSet $description failed to become ready within ${timeout}s"
    kubectl get statefulset "$name" -n "$namespace" || true
    kubectl describe statefulset "$name" -n "$namespace" || true
    return 1
}

# =============================================================================
# Check Prerequisites
# =============================================================================
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
log_info "Verifying Kubernetes cluster connection..."

if ! kubectl cluster-info &> /dev/null; then
    log_error "Cannot connect to Kubernetes cluster"
    echo ""
    log_info "Please run: ./00-install-k3s.sh"
    exit 1
fi

CURRENT_CLUSTER=$(kubectl config current-context 2>/dev/null || echo "unknown")
log_success "Connected to cluster: $CURRENT_CLUSTER"
echo ""

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

# =============================================================================
# Generate Secrets
# =============================================================================
log_info "Generating secure secrets..."
POSTGRES_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
JWT_SECRET=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
ADMIN_API_KEY=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
MINIO_PASSWORD=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
log_success "Secrets generated"
echo ""

# =============================================================================
# Create Namespace
# =============================================================================
log_info "Creating namespace..."
kubectl apply -f "$K8S_DIR/00-namespace.yaml"
echo ""

# =============================================================================
# Create ConfigMap
# =============================================================================
log_info "Creating ConfigMap..."
kubectl apply -f "$K8S_DIR/01-configmap.yaml"
echo ""

# =============================================================================
# Create Secrets
# =============================================================================
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

# =============================================================================
# Create PVCs
# =============================================================================
log_info "Creating Persistent Volume Claims..."
kubectl apply -f "$K8S_DIR/03-pvcs.yaml"
echo ""

# =============================================================================
# Deploy PostgreSQL Primary
# =============================================================================
log_info "Deploying PostgreSQL Primary..."
kubectl apply -f "$K8S_DIR/04-postgres-primary.yaml"

if ! wait_for_statefulset_ready "postgres-primary" "portfolio" 180 "PostgreSQL Primary"; then
    log_error "PostgreSQL Primary failed to start"
    kubectl logs -n portfolio -l app=postgres-primary --tail=50 || true
    exit 1
fi
echo ""

# Create replication slot and extensions
log_info "Configuring PostgreSQL Primary..."

# Wait a bit for postgres to be fully ready for connections
sleep 5

kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT pg_create_physical_replication_slot('replica_slot_1') WHERE NOT EXISTS (SELECT 1 FROM pg_replication_slots WHERE slot_name = 'replica_slot_1');" \
  2>/dev/null || log_warn "Replication slot may already exist"

kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;" \
  2>/dev/null || true

kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c "CREATE EXTENSION IF NOT EXISTS pg_cron;" \
  2>/dev/null || true

log_success "PostgreSQL Primary configured"
echo ""

# =============================================================================
# Deploy PostgreSQL Replica
# =============================================================================
log_info "Deploying PostgreSQL Replica..."
kubectl apply -f "$K8S_DIR/05-postgres-replica.yaml"

if ! wait_for_statefulset_ready "postgres-replica" "portfolio" 300 "PostgreSQL Replica"; then
    log_warn "PostgreSQL Replica not ready - backend will fall back to primary"
    log_info "Check replica logs with: kubectl logs -n portfolio postgres-replica-0"
else
    # Verify replication
    log_info "Verifying replication status..."
    kubectl exec -n portfolio postgres-primary-0 -- \
      psql -U postgres -d portfolio -c "SELECT client_addr, state, sync_state FROM pg_stat_replication;" \
      2>/dev/null || log_warn "Could not verify replication"
fi
echo ""

# =============================================================================
# Deploy Redis
# =============================================================================
log_info "Deploying Redis..."
kubectl apply -f "$K8S_DIR/06-redis.yaml"
if ! wait_for_pods_ready "app=redis" "portfolio" 60 "Redis"; then
    log_error "Redis failed to start"
    exit 1
fi
echo ""

# =============================================================================
# Deploy MinIO
# =============================================================================
log_info "Deploying MinIO..."
kubectl apply -f "$K8S_DIR/07-minio.yaml"
if ! wait_for_pods_ready "app=minio" "portfolio" 60 "MinIO"; then
    log_error "MinIO failed to start"
    exit 1
fi
echo ""

# =============================================================================
# Deploy Image Service (2 replicas)
# =============================================================================
log_info "Deploying Image Service (2 replicas)..."
kubectl apply -f "$K8S_DIR/08-image-service.yaml"
if ! wait_for_pods_ready "app=image-service" "portfolio" 180 "Image Service"; then
    log_error "Image Service failed to start"
    exit 1
fi
echo ""

# =============================================================================
# Deploy Backend (2 replicas)
# =============================================================================
log_info "Deploying Backend (2 replicas with read/write splitting)..."
kubectl apply -f "$K8S_DIR/09-backend.yaml"
if ! wait_for_pods_ready "app=backend" "portfolio" 240 "Backend"; then
    log_error "Backend failed to start"
    kubectl logs -n portfolio -l app=backend --tail=50 || true
    exit 1
fi
echo ""

# =============================================================================
# Deploy Nginx
# =============================================================================
log_info "Deploying Nginx..."
kubectl apply -f "$K8S_DIR/10-nginx.yaml"
if ! wait_for_pods_ready "app=nginx" "portfolio" 60 "Nginx"; then
    log_error "Nginx failed to start"
    exit 1
fi
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

# Get LoadBalancer IP/Port
LOADBALANCER_IP=$(kubectl get svc nginx -n portfolio -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
NODEPORT=$(kubectl get svc nginx -n portfolio -o jsonpath='{.spec.ports[0].nodePort}' 2>/dev/null || echo "")

if [ -z "$LOADBALANCER_IP" ]; then
    # k3s ServiceLB - get node IP
    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
    LOADBALANCER_IP="$NODE_IP"
fi

echo ""
echo "=================================="
echo "Access Information"
echo "=================================="
echo ""
echo "Application URL: http://$LOADBALANCER_IP:$NODEPORT"
echo "API Documentation: http://$LOADBALANCER_IP:$NODEPORT/docs"
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
echo "   kubectl exec -n portfolio postgres-primary-0 -- psql -U postgres -d portfolio -c 'SELECT * FROM pg_stat_replication;'"
echo ""
echo "4. Check replica is in recovery mode:"
echo "   kubectl exec -n portfolio postgres-replica-0 -- psql -U postgres -d postgres -c 'SELECT pg_is_in_recovery();'"
echo ""
echo "5. View logs:"
echo "   kubectl logs -n portfolio deployment/backend -f"
echo "   kubectl logs -n portfolio deployment/image-service -f"
echo ""
echo "=================================="