#!/bin/bash
set -e

# =============================================================================
# rolling-deploy.sh — Smart rolling update for an already-running cluster
#
# What this does vs deploy-k3s-local.sh:
#
#   deploy-k3s-local.sh  → fresh install, generates NEW secrets, waits from zero
#   rolling-deploy.sh    → running cluster, REUSES existing secrets, rolling restart
#
# WHY secrets must be reused:
#   PostgreSQL stores its own password hash in the data directory.
#   If you generate a new POSTGRES_PASSWORD and push it as a new Kubernetes
#   secret, the app gets the new password but the database still expects the
#   old one. Every connection fails. Reusing .credentials avoids this entirely.
#
# WHY some deployments use Recreate instead of RollingUpdate:
#   ReadWriteOnce PVCs can only be mounted by ONE pod at a time on the same node.
#   RollingUpdate tries to create the new pod BEFORE killing the old one.
#   Both pods fight over the same RWO PVC → new pod stuck in ContainerCreating
#   → deadlock. Affected services: Redis, MinIO, LibreTranslate, Grafana.
#   These use strategy: Recreate in their manifests — old pod dies first, then
#   new pod mounts the PVC cleanly. Brief downtime on those services only.
#   StatefulSets (Postgres, Redpanda, Loki) handle this correctly by design.
#
# What gets updated:
#   - ConfigMaps (always safe, applied immediately)
#   - Kubernetes Secrets (rewritten with the SAME values from .credentials)
#   - All manifests via kubectl apply
#   - Custom-image Deployments force-restarted so pods pick up the new image
#
# What is deliberately left alone:
#   - PersistentVolumeClaims (never touched — data lives here)
#   - StatefulSet pod restarts (kubectl apply handles via rolling update on spec change)
#   - Official images (postgres, redis, minio, etc.) unless their tag changed
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

export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

echo "============================================"
echo "Rolling Deploy"
echo "============================================"
echo ""

# =============================================================================
# Preflight: cluster must already be running
# =============================================================================
if ! kubectl cluster-info &>/dev/null; then
    log_error "Cannot reach k3s cluster. Is it running?"
    log_error "Run deploy-k3s-local.sh for a fresh install."
    exit 1
fi

if ! kubectl get namespace portfolio &>/dev/null; then
    log_error "Namespace 'portfolio' does not exist."
    log_error "Run deploy-k3s-local.sh for a fresh install."
    exit 1
fi

# =============================================================================
# Load existing credentials — never generate new ones on a rolling deploy
# =============================================================================
CREDENTIALS_FILE="${SCRIPT_DIR}/.credentials"

if [ ! -f "$CREDENTIALS_FILE" ]; then
    log_error ".credentials not found at $CREDENTIALS_FILE"
    log_error "This file is created by deploy-k3s-local.sh on first install."
    log_error "Run deploy-k3s-local.sh first, then use rolling-deploy.sh for updates."
    exit 1
fi

log_info "Loading credentials from .credentials..."
POSTGRES_PASSWORD=$(grep '^POSTGRES_PASSWORD=' "$CREDENTIALS_FILE" | cut -d= -f2-)
JWT_SECRET=$(grep '^JWT_SECRET='         "$CREDENTIALS_FILE" | cut -d= -f2-)
MINIO_PASSWORD=$(grep '^MINIO_PASSWORD=' "$CREDENTIALS_FILE" | cut -d= -f2-)
RESEND_KEY=$(grep '^RESEND_API_KEY='     "$CREDENTIALS_FILE" | cut -d= -f2-)

if [ -z "$POSTGRES_PASSWORD" ] || [ -z "$JWT_SECRET" ] || [ -z "$MINIO_PASSWORD" ]; then
    log_error ".credentials is missing required fields (POSTGRES_PASSWORD, JWT_SECRET, MINIO_PASSWORD)."
    exit 1
fi
log_success "Credentials loaded"

GRAFANA_ADMIN_PASS_FILE="${SCRIPT_DIR}/.grafana-admin-password"
GRAFANA_DEMO_PASS_FILE="${SCRIPT_DIR}/.grafana-demo-password"

if [ ! -f "$GRAFANA_ADMIN_PASS_FILE" ] || [ ! -f "$GRAFANA_DEMO_PASS_FILE" ]; then
    log_error "Grafana password files not found."
    log_error "Expected: .grafana-admin-password and .grafana-demo-password in k8s scripts/"
    exit 1
fi

GRAFANA_ADMIN_PASS=$(cat "$GRAFANA_ADMIN_PASS_FILE")
GRAFANA_DEMO_PASS=$(cat "$GRAFANA_DEMO_PASS_FILE")
log_success "Grafana passwords loaded"
echo ""

# =============================================================================
# Helper: wait for a Deployment rollout to finish
# =============================================================================
wait_rollout() {
    local name="$1"
    local timeout="${2:-300}"
    log_info "Waiting for $name rollout (max ${timeout}s)..."
    if kubectl rollout status deployment/"$name" -n portfolio --timeout="${timeout}s"; then
        log_success "$name is healthy"
    else
        log_error "$name rollout failed"
        kubectl describe deployment "$name" -n portfolio | tail -20
        return 1
    fi
}

# =============================================================================
# Step 1: ConfigMap
# =============================================================================
log_info "Applying ConfigMap..."
kubectl apply -f "$K8S_DIR/01-configmap.yaml"
kubectl patch configmap portfolio-config -n portfolio --type merge \
  -p "{\"data\":{\"ALLOWED_ORIGINS\":\"[\\\"http://localhost\\\",\\\"http://localhost:80\\\",\\\"https://testproveoportfolio.xyz\\\",\\\"https://www.testproveoportfolio.xyz\\\"]\"}}"
log_success "ConfigMap updated"
echo ""

# =============================================================================
# Step 2: Secrets — rewrite with the SAME values from .credentials
# =============================================================================
log_info "Refreshing secrets (same passwords, no rotation)..."

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
  --from-literal=API_BASE_URL="https://testproveoportfolio.xyz" \
  -n portfolio \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic monitoring-secrets \
  --from-literal=GF_SECURITY_ADMIN_USER=admin \
  --from-literal=GF_SECURITY_ADMIN_PASSWORD="$GRAFANA_ADMIN_PASS" \
  --from-literal=GF_DEMO_PASSWORD="$GRAFANA_DEMO_PASS" \
  -n portfolio \
  --dry-run=client -o yaml | kubectl apply -f -

log_success "Secrets refreshed"
echo ""

# =============================================================================
# Step 3: Apply all manifests
#
# kubectl apply is the right tool here:
#   - Deployments with RollingUpdate: triggers rolling restart if spec changed.
#     Custom-image deployments (backend, nginx, etc.) get force-restarted in
#     Step 4 below because :latest tag changes are invisible to kubectl.
#   - Deployments with Recreate (Redis, MinIO, LibreTranslate, Grafana): kills
#     the old pod first, then creates the new one — safe for RWO PVCs.
#   - StatefulSets (Postgres, Redpanda, Loki): updates spec, handles PVCs by
#     design, never touches volumeClaimTemplates.
#   - Services / ConfigMaps: in-place update, zero downtime.
#
# Skipped:
#   - 02-secrets.yaml: template only, real secrets are managed above
#   - 03-pvcs.yaml: PVCs are never deleted or recreated on rolling deploy.
#     kubectl apply on an existing PVC is effectively a no-op for the data,
#     but we skip it explicitly to make intent clear — storage is untouched.
#   - 12-redpanda-init.yaml: topics already exist, no need to re-run.
#     If you add a new topic, run this manually after deploy.
#
# Grafana init Job:
#   Jobs are immutable in Kubernetes — kubectl apply fails if it already exists.
#   We delete it first so the apply recreates it cleanly. It's idempotent:
#   if the demo user already exists it updates the password, otherwise creates.
# =============================================================================
log_info "Applying manifests..."

# Delete the Grafana init Job before applying monitoring (Jobs are immutable)
kubectl delete job grafana-init-users -n portfolio 2>/dev/null \
    && log_info "  deleted stale grafana-init-users Job" \
    || log_info "  grafana-init-users Job not found (first deploy or already cleaned up)"

for manifest in \
    04-postgres-primary.yaml \
    05-postgres-replica.yaml \
    06-redis.yaml \
    07-minio.yaml \
    08-image-service.yaml \
    09-backend.yaml \
    10-nginx.yaml \
    11-redpanda.yaml \
    13-consumer.yaml \
    14-temporal.yaml \
    15-temporal-worker.yaml \
    16-libretranslate.yaml \
    17-monitoring.yaml; do
    kubectl apply -f "$K8S_DIR/$manifest"
    log_success "  applied $manifest"
done

echo ""

# =============================================================================
# Step 4: Force-restart Deployments that use custom-built images
#
# kubectl apply only triggers a rolling restart when the pod template spec
# changes. Since we use :latest tags, kubectl cannot detect the image changed
# — we have to tell it explicitly via rollout restart.
#
# rollout restart patches the pod template with a restart annotation, which
# triggers the strategy defined in each manifest:
#   - backend, image-service, nginx, consumer, temporal-worker:
#     RollingUpdate (maxSurge:1, maxUnavailable:0) — no downtime
#
# Services with Recreate strategy (Redis, MinIO, LibreTranslate, Grafana) are
# NOT in this list. They use official images so they don't need force-restart.
# If their manifests changed, kubectl apply in Step 3 already handled it.
# =============================================================================
log_info "Force-restarting deployments with custom images..."

CUSTOM_DEPLOYMENTS=(
    backend
    image-service
    nginx
    consumer
    temporal-worker
)

for deployment in "${CUSTOM_DEPLOYMENTS[@]}"; do
    kubectl rollout restart deployment/"$deployment" -n portfolio
    log_info "  restart triggered: $deployment"
done

echo ""

# Restart Loki and Alloy so they always pick up ConfigMap changes.
# Grafana already restarts every deploy because of Recreate strategy.
# Loki won't hot-reload its config file — it needs an actual pod restart.
# Alloy same story. Both are fast to come back up.
log_info "Restarting Loki and Alloy (ConfigMap changes)..."
kubectl rollout restart statefulset/loki -n portfolio
kubectl rollout restart daemonset/alloy -n portfolio
log_success "Loki and Alloy restarts triggered"
echo ""

# =============================================================================
# Step 5: Wait for rollouts
# =============================================================================
log_info "Waiting for rollouts to complete..."
echo ""

for deployment in "${CUSTOM_DEPLOYMENTS[@]}"; do
    wait_rollout "$deployment" 300
done

log_info "Waiting for Loki rollout..."
if kubectl rollout status statefulset/loki -n portfolio --timeout=120s; then
    log_success "Loki is healthy"
else
    log_warn "Loki rollout did not complete in time — check: kubectl logs -n portfolio -l app=loki"
fi

log_info "Waiting for Alloy rollout..."
if kubectl rollout status daemonset/alloy -n portfolio --timeout=120s; then
    log_success "Alloy is healthy"
else
    log_warn "Alloy rollout did not complete in time — check: kubectl logs -n portfolio -l app=alloy"
fi

# Wait for Grafana init Job
log_info "Waiting for Grafana user init Job..."
if kubectl wait --for=condition=complete job/grafana-init-users -n portfolio --timeout=120s; then
    log_success "Grafana users initialized"
else
    log_warn "Grafana init Job did not complete in time — demo user may need manual re-run"
    log_warn "  kubectl delete job grafana-init-users -n portfolio"
    log_warn "  kubectl apply -f k8s/17-monitoring.yaml"
fi

echo ""

# =============================================================================
# Step 6: Sanity check
# =============================================================================
log_info "Pod status:"
kubectl get pods -n portfolio -o wide
echo ""

NOT_RUNNING=$(kubectl get pods -n portfolio --no-headers \
    | grep -v -E 'Running|Completed' \
    | grep -v '^$' || true)

if [ -n "$NOT_RUNNING" ]; then
    log_warn "Some pods are not in Running/Completed state:"
    echo "$NOT_RUNNING"
else
    log_success "All pods are Running or Completed"
fi

echo ""
echo "============================================"
echo "  Rolling deploy complete"
echo "============================================"
echo ""
echo "  Frontend: https://testproveoportfolio.xyz/front-page/front-page.html"
echo "  Health:   https://testproveoportfolio.xyz/health"
echo "  Grafana:  https://testproveoportfolio.xyz/grafana"
echo ""