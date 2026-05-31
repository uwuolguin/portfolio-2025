#!/bin/bash
set -e

# =============================================================================
# Portfolio k3s Deployment Script - DigitalOcean 4GB Droplet
# Run as regular user with sudo -n privileges
# Deploys services SEQUENTIALLY to avoid OOM
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

log_info "SCRIPT_DIR=$SCRIPT_DIR"
log_info "PROJECT_ROOT=$PROJECT_ROOT"
log_info "K8S_DIR=$K8S_DIR"

echo "============================================"
echo "Portfolio Deployment - DO 4GB Droplet"
echo "============================================"
echo ""
echo "K8s manifests: $K8S_DIR"
echo ""

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
    sudo -n cp /etc/rancher/k3s/k3s.yaml "$HOME/.kube/config"
    sudo -n chown "$USER:$(id -gn)" "$HOME/.kube/config"
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
        local desired=$(kubectl get deployment "$name" -n "$namespace" \
            -o jsonpath='{.spec.replicas}' 2>/dev/null)
        local ready=$(kubectl get deployment "$name" -n "$namespace" \
            -o jsonpath='{.status.readyReplicas}' 2>/dev/null)

        desired="${desired:-1}"
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
        local ready=$(kubectl get statefulset "$name" -n "$namespace" -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
        local desired=$(kubectl get statefulset "$name" -n "$namespace" -o jsonpath='{.spec.replicas}' 2>/dev/null)

        desired="${desired:-1}"
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
            -o jsonpath='{.items[*].status.containerStatuses[*].ready}' 2>/dev/null | tr ' ' '\n' | grep -c "true")
        local total=$(kubectl get pods -n "$namespace" -l "$selector" \
            --no-headers 2>/dev/null | wc -l | tr -d ' ')

        ready="${ready:-0}"
        total="${total:-0}"

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
    log_error "Make sure k3s is running: sudo -n systemctl status k3s"
    log_error "And kubeconfig exists: ls -la $HOME/.kube/config"
    exit 1
fi

MISSING=0
for img in portfolio-backend:latest portfolio-image-service:latest portfolio-nginx:latest portfolio-postgres:16; do
    if ! sudo -n k3s ctr images ls | grep -q "$img"; then
        log_error "Missing image: $img"
        MISSING=1
    fi
done
if [ "$MISSING" -eq 1 ]; then
    log_error "Run build-and-import-k3s.sh first"
    exit 1
fi

# =============================================================================
# Check Grafana password files
# =============================================================================
GRAFANA_ADMIN_PASS_FILE="${SCRIPT_DIR}/.grafana-admin-password"
GRAFANA_DEMO_PASS_FILE="${SCRIPT_DIR}/.grafana-demo-password"

if [ ! -f "$GRAFANA_ADMIN_PASS_FILE" ]; then
    log_info "Grafana admin password file not found — enter it now (input hidden):"
    read -rsp "  Admin password: " GRAFANA_ADMIN_PASS_INPUT
    echo ""
    # printf '%s' avoids the trailing \n that echo adds — password stays clean
    printf '%s' "$GRAFANA_ADMIN_PASS_INPUT" > "$GRAFANA_ADMIN_PASS_FILE"
    chmod 600 "$GRAFANA_ADMIN_PASS_FILE"
    log_success "Saved to $GRAFANA_ADMIN_PASS_FILE"
fi

if [ ! -f "$GRAFANA_DEMO_PASS_FILE" ]; then
    log_info "Grafana demo password file not found — enter it now (input hidden):"
    read -rsp "  Demo password: " GRAFANA_DEMO_PASS_INPUT
    echo ""
    # printf '%s' avoids the trailing \n that echo adds — password stays clean
    printf '%s' "$GRAFANA_DEMO_PASS_INPUT" > "$GRAFANA_DEMO_PASS_FILE"
    chmod 600 "$GRAFANA_DEMO_PASS_FILE"
    log_success "Saved to $GRAFANA_DEMO_PASS_FILE"
fi

# tr -d '\n' strips any trailing newline so the password value is clean
GRAFANA_ADMIN_PASS=$(tr -d '\n' < "$GRAFANA_ADMIN_PASS_FILE")
GRAFANA_DEMO_PASS=$(tr -d '\n' < "$GRAFANA_DEMO_PASS_FILE")

log_success "All prerequisites OK"
echo ""

# =============================================================================
# Generate or load secrets (idempotent)
# If portfolio-secrets already exists in the cluster, read values back from it
# so existing Postgres data, MinIO buckets, and JWT tokens all stay valid.
# On a first deploy the secret does not exist yet — generate fresh values.
# =============================================================================
if kubectl get secret portfolio-secrets -n portfolio &>/dev/null 2>&1; then
    log_info "portfolio-secrets already exists — loading from cluster (idempotent run)"
    POSTGRES_PASSWORD=$(kubectl get secret portfolio-secrets -n portfolio \
        -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
    JWT_SECRET=$(kubectl get secret portfolio-secrets -n portfolio \
        -o jsonpath='{.data.SECRET_KEY}' | base64 -d)
    MINIO_PASSWORD=$(kubectl get secret portfolio-secrets -n portfolio \
        -o jsonpath='{.data.MINIO_ROOT_PASSWORD}' | base64 -d)
    log_success "Secrets loaded from cluster"
else
    log_info "Generating new secrets (first deploy)..."
    POSTGRES_PASSWORD=$(openssl rand -hex 16)
    JWT_SECRET=$(openssl rand -hex 16)
    MINIO_PASSWORD=$(openssl rand -hex 16)
    log_success "New secrets generated"
fi

# =============================================================================
# Load Resend API key from .env.secrets
# Parsed line-by-line — never sourced — so no arbitrary shell execution.
# Only strict KEY=value lines (no spaces around =) are accepted.
#
# "read" strips the trailing \n naturally, so RESEND_KEY will be exactly
# "re_yourkeyhere" with no trailing newline — safe to pass directly into
# kubectl secrets.
#
# Test:
#   printf 'RESEND_API_KEY=re_test123\n' > /tmp/t.env && \
#   RESEND_KEY="" && \
#   while IFS= read -r line || [ -n "$line" ]; do
#     [[ "$line" =~ ^RESEND_API_KEY=(re_.+)$ ]] || continue
#     RESEND_KEY="${BASH_REMATCH[1]}"
#   done < /tmp/t.env && \
#   echo "key='$RESEND_KEY'" && \   # → key='re_test123' (no trailing \n)
#   rm /tmp/t.env
# =============================================================================

# Starts empty; -z check below catches "file exists but key missing"
RESEND_KEY=""

if [ -f "${SCRIPT_DIR}/.env.secrets" ]; then

    log_info "Loading Resend API key from .env.secrets"

    # IFS=              → preserves leading/trailing spaces in the value
    # read -r           → backslashes are treated literally
    # || [ -n "$line" ] → rescues final line if file has no trailing \n
    while IFS= read -r line || [ -n "$line" ]; do

        [[ "$line" =~ ^[[:space:]]*$ ]] && continue  # skip blank lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue  # skip comments

        # BASH_REMATCH[0] = entire matched line
        # BASH_REMATCH[1] = captured API key value (re_...)
        if [[ "$line" =~ ^RESEND_API_KEY=(re_.+)$ ]]; then
            RESEND_KEY="${BASH_REMATCH[1]}"
        else
            log_warn ".env.secrets: ignoring malformed line: $line"
        fi

    # Redirect file into loop stdin without a subshell,
    # so RESEND_KEY survives after the loop exits.
    done < "${SCRIPT_DIR}/.env.secrets"

    #-z tests whether a string is empty.
    if [ -z "$RESEND_KEY" ]; then
        log_error "RESEND_API_KEY missing from .env.secrets"
        exit 1
    fi

    log_success "Resend API key loaded"

else
    log_error ".env.secrets not found — run ./set-resend-key.sh first"
    exit 1
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
# Deploy step by step
# =============================================================================

# Namespace
log_info "Creating namespace..."
kubectl apply -f "$K8S_DIR/00-namespace.yaml"
echo ""

# TLS secret
log_info "Loading TLS certificates into cluster..."

if [ -f "/home/deploy/certs/fullchain.pem" ] && [ -f "/home/deploy/certs/privkey.pem" ]; then

    # Idempotent secret creation/update:
    #
    # --dry-run=client
    #   Generates the Secret manifest locally without creating it in the cluster.
    #
    # -o yaml
    #   Outputs the generated Secret manifest as YAML.
    #
    # kubectl apply -f -
    #   Reads the YAML from stdin ("-") and applies it declaratively:
    #   - creates the Secret if it does not exist
    #   - updates the Secret if it already exists
    #
    # This makes the operation idempotent because re-running the script
    # converges the cluster to the same desired Secret state instead of
    # failing with "AlreadyExists".

    kubectl create secret tls tls-secret \
        --cert=/home/deploy/certs/fullchain.pem \
        --key=/home/deploy/certs/privkey.pem \
        -n portfolio \
        --dry-run=client -o yaml | kubectl apply -f -

    log_success "TLS secret loaded"
else
    log_error "TLS certs not found at /home/deploy/certs/"
    log_error "Run certbot first (see SSL_SETUP.md Steps 1-4), then re-run this script"
    exit 1
fi

echo ""

# ConfigMap
log_info "Creating ConfigMap..."
kubectl apply -f "$K8S_DIR/01-configmap.yaml"
echo ""

# Secrets
# --dry-run=client -o yaml generates the Secret manifest locally without creating it.
# The generated YAML is piped to `kubectl apply -f -`.
#
# -f means "read manifest from file" (--filename).
# The final `-` is a Unix convention meaning stdin, so kubectl treats
# the piped stdin stream as the input file.
#
# `apply` makes the operation idempotent:
# - creates the Secret if missing
# - updates it if it already exists
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
  --from-literal=API_BASE_URL="https://testproveoportfolio.xyz" \
  -n portfolio \
  --dry-run=client -o yaml | kubectl apply -f -

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
    kubectl logs -n portfolio postgres-primary-0 -c postgres --tail=30 2>/dev/null || true
    exit 1
fi

sleep 5
kubectl exec -n portfolio postgres-primary-0 -c postgres -- \
  env PGPASSWORD="$POSTGRES_PASSWORD" \
  psql -U postgres -d portfolio -c \
  "SELECT pg_create_physical_replication_slot('replica_slot_1')
   WHERE NOT EXISTS (
     SELECT 1
     FROM pg_replication_slots
     WHERE slot_name = 'replica_slot_1'
   );" \
  2>/dev/null || true

kubectl exec -n portfolio postgres-primary-0 -c postgres -- \
  env PGPASSWORD="$POSTGRES_PASSWORD" \
  psql -U postgres -d portfolio -c \
  "CREATE EXTENSION IF NOT EXISTS pg_trgm;" \
  2>/dev/null || true

kubectl exec -n portfolio postgres-primary-0 -c postgres -- \
  env PGPASSWORD="$POSTGRES_PASSWORD" \
  psql -U postgres -d portfolio -c \
  "CREATE EXTENSION IF NOT EXISTS pg_cron;" \
  2>/dev/null || true

log_success "PostgreSQL Primary configured"
echo ""

# =============================================================================
# PostgreSQL Replica
# =============================================================================
log_info "Deploying PostgreSQL Replica..."
kubectl apply -f "$K8S_DIR/05-postgres-replica.yaml"

if ! wait_for_statefulset_ready "postgres-replica" "portfolio" 300 "PostgreSQL Replica"; then
    log_warn "Replica not ready - backend will use primary for reads"
    log_warn "Check: kubectl logs -n portfolio postgres-replica-0 -c postgres"
fi

log_info "Verifying replication state..."
sleep 10

REPL_STATE=$(kubectl exec -n portfolio postgres-primary-0 -c postgres -- \
  env PGPASSWORD="$POSTGRES_PASSWORD" \
  psql -U postgres -d portfolio -tAc \
  "SELECT state FROM pg_stat_replication WHERE application_name = 'replica1';" \
  2>/dev/null || echo "error")

if [ "$REPL_STATE" = "streaming" ]; then
    log_success "Replication active (replica1 is streaming)"
else
    log_warn "Replication state: '$REPL_STATE' (expected 'streaming')"
    log_warn "Check: kubectl logs -n portfolio postgres-replica-0 -c postgres"
fi

RECOVERY=$(kubectl exec -n portfolio postgres-replica-0 -c postgres -- \
  env PGPASSWORD="$POSTGRES_PASSWORD" \
  psql -U postgres -d postgres -tAc \
  "SELECT pg_is_in_recovery();" \
  2>/dev/null || echo "error")

if [ "$RECOVERY" = "t" ]; then
    log_success "Replica is in recovery mode (standby confirmed)"
else
    log_warn "Replica pg_is_in_recovery() returned: '$RECOVERY' (expected 't')"
fi

echo ""

# =============================================================================
# Redis
# =============================================================================
log_info "Deploying Redis..."
kubectl apply -f "$K8S_DIR/06-redis.yaml"
if ! wait_for_pods_ready "app=redis" "portfolio" 60 "Redis"; then
    log_warn "Redis not ready — cache and rate limiting will be unavailable"
else
    REDIS_PING=$(kubectl exec -n portfolio deployment/redis -- redis-cli ping 2>/dev/null || echo "error")
    if [ "$REDIS_PING" = "PONG" ]; then
        log_success "Redis accepting connections"
    else
        log_warn "Redis ping returned: '$REDIS_PING' (expected 'PONG')"
    fi
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

MINIO_HEALTH=$(kubectl exec -n portfolio deployment/minio -- \
  curl -s -o /dev/null -w "%{http_code}" http://localhost:9000/minio/health/ready \
  2>/dev/null || echo "error")

if [ "$MINIO_HEALTH" = "200" ]; then
    log_success "MinIO healthy (HTTP 200)"
else
    log_warn "MinIO health check returned: '$MINIO_HEALTH' (expected '200')"
fi
echo ""

# =============================================================================
# LibreTranslate
# =============================================================================
log_info "Deploying LibreTranslate (self-hosted translation)..."
kubectl apply -f "$K8S_DIR/16-libretranslate.yaml"

log_info "Waiting for LibreTranslate — first boot downloads language models, allow 2-3 minutes..."
if ! wait_for_pods_ready "app=libretranslate" "portfolio" 300 "LibreTranslate"; then
    log_error "LibreTranslate failed"
    kubectl logs -n portfolio -l app=libretranslate --tail=30 2>/dev/null || true
    exit 1
fi

log_info "Testing LibreTranslate en→es..."
# libretranslate has no curl in its image so kubectl exec won't work here.
# Instead a throwaway pod (curlimages/curl) is created inside the portfolio
# namespace — it shares the same cluster network so libretranslate:5000
# resolves via ClusterIP DNS exactly as the backend would hit it in production.
# --rm deletes the pod the moment curl exits, no manual cleanup needed.
# --restart=Never prevents Kubernetes from restarting it if curl fails.
# -i attaches stdin so the pod output is streamed back to this shell.
RESULT_ES=$(kubectl run curl-test-es --image=curlimages/curl:latest \
  --rm --restart=Never -i -n portfolio -- \
  curl -s -X POST http://libretranslate:5000/translate \
  -H "Content-Type: application/json" \
  -d '{"q":"hello","source":"en","target":"es","format":"text"}' \
  2>/dev/null || echo "error")

if echo "$RESULT_ES" | grep -q "hola"; then
    log_success "en→es working (hello → hola)"
else
    log_error "en→es failed, got: '$RESULT_ES'"
    exit 1
fi

log_info "Testing LibreTranslate es→en..."
RESULT_EN=$(kubectl run curl-test-en --image=curlimages/curl:latest \
  --rm --restart=Never -i -n portfolio -- \
  curl -s -X POST http://libretranslate:5000/translate \
  -H "Content-Type: application/json" \
  -d '{"q":"hola","source":"es","target":"en","format":"text"}' \
  2>/dev/null || echo "error")

if echo "$RESULT_EN" | grep -q "hello"; then
    log_success "es→en working (hola → hello)"
else
    log_error "es→en failed, got: '$RESULT_EN'"
    exit 1
fi

echo ""

# =============================================================================
# Image Service
# =============================================================================
log_info "Deploying Image Service (NSFW enabled)..."
kubectl apply -f "$K8S_DIR/08-image-service.yaml"
if ! wait_for_pods_ready "app=image-service" "portfolio" 120 "Image Service"; then
    log_error "Image Service failed"; exit 1
fi

log_info "Testing Image Service health..."
IMAGE_HEALTH=$(kubectl run curl-test-image --image=curlimages/curl:latest \
  --rm --restart=Never -i -n portfolio -- \
  curl -s -o /dev/null -w "%{http_code}" http://image-service:8080/health \
  2>/dev/null | grep -o '^[0-9]*')

if [ "$IMAGE_HEALTH" = "200" ]; then
    log_success "Image Service healthy (HTTP 200)"
else
    log_error "Image Service health check returned: '$IMAGE_HEALTH' (expected 200)"
    exit 1
fi

# =============================================================================
# Temporal Server + UI
# =============================================================================
log_info "Deploying Temporal server and UI..."
kubectl apply -f "$K8S_DIR/14-temporal.yaml"

if ! wait_for_pods_ready "app=temporal" "portfolio" 120 "Temporal server"; then
    log_error "Temporal server failed"
    kubectl logs -n portfolio -l app=temporal -c temporal --tail=30 2>/dev/null || true
    exit 1
fi

log_info "Verifying Temporal server health..."

# tctl is the Temporal CLI — ships inside the temporal server image.
# `cluster health` hits the server's gRPC health endpoint and returns
# the state of each internal service (frontend, history, matching, worker).
# All four must report SERVING for the cluster to be operational.
TEMPORAL_POD=$(kubectl get pods -n portfolio -l app=temporal -o jsonpath='{.items[0].metadata.name}')
TEMPORAL_HEALTH=$(kubectl exec -n portfolio "$TEMPORAL_POD" -c temporal -- \
  tctl cluster health 2>/dev/null || echo "error")

if echo "$TEMPORAL_HEALTH" | grep -qi "serving"; then
    log_success "Temporal server healthy"
else
    log_warn "Temporal health returned: '$TEMPORAL_HEALTH'"
fi

log_info "Verifying Temporal UI..."
TEMPORAL_UI_POD=$(kubectl get pods -n portfolio -l app=temporal-ui -o jsonpath='{.items[0].metadata.name}')

# --spider skips downloading the body and only checks the HTTP status code.
# The UI is a Svelte SPA — the HTML body contains no identifiable text to grep,
# so checking the exit code (0 = 200 OK) is the only reliable signal here.
if kubectl exec -n portfolio "$TEMPORAL_UI_POD" -c temporal-ui -- \
  wget -q --spider http://localhost:8080 2>/dev/null; then
    log_success "Temporal UI responding"
else
    log_warn "Temporal UI not responding on localhost:8080"
fi
echo ""

# =============================================================================
# Temporal Worker
# =============================================================================
log_info "Deploying Temporal worker..."
kubectl apply -f "$K8S_DIR/15-temporal-worker.yaml"

if ! wait_for_deployment_ready "temporal-worker" "portfolio" 120 "Temporal worker"; then
    log_error "Temporal worker failed"
    kubectl logs -n portfolio -l app=temporal-worker -c temporal-worker --tail=30 2>/dev/null || true
    exit 1
fi

log_info "Verifying Temporal worker registered task queue..."
WORKER_LOGS=$(kubectl logs -n portfolio -l app=temporal-worker -c temporal-worker --tail=20 2>/dev/null || echo "error")

if echo "$WORKER_LOGS" | grep -q "temporal_worker_polling"; then
    log_success "Temporal worker polling auth-queue"
else
    log_warn "Could not confirm worker task queue registration — check logs:"
    log_warn "  kubectl logs -n portfolio -l app=temporal-worker -c temporal-worker"
fi

# =============================================================================
# Redpanda
# =============================================================================
log_info "Deploying Redpanda..."
kubectl apply -f "$K8S_DIR/11-redpanda.yaml"

if ! wait_for_statefulset_ready "redpanda" "portfolio" 120 "Redpanda"; then
    log_error "Redpanda failed"
    kubectl logs -n portfolio redpanda-0 -c redpanda --tail=30 2>/dev/null || true
    exit 1
fi

log_info "Verifying Redpanda cluster health..."
REDPANDA_HEALTH=$(kubectl exec -n portfolio redpanda-0 -c redpanda -- \
  rpk cluster health 2>/dev/null || echo "error")

if echo "$REDPANDA_HEALTH" | grep -qi "healthy"; then
    log_success "Redpanda cluster healthy"
else
    log_warn "Redpanda health returned: '$REDPANDA_HEALTH'"
fi
echo ""

# =============================================================================
# Redpanda Init (topic creation)
# =============================================================================
log_info "Running Redpanda init Job (creating topics)..."
kubectl apply -f "$K8S_DIR/12-redpanda-init.yaml"

if ! kubectl wait --for=condition=complete job/redpanda-init -n portfolio --timeout=60s; then
    log_error "Redpanda init Job failed"
    kubectl logs -n portfolio -l job-name=redpanda-init --tail=30 2>/dev/null || true
    exit 1
fi

sleep 5

log_info "Verifying Redpanda topics..."
TOPICS=$(kubectl exec -n portfolio redpanda-0 -c redpanda -- \
  rpk topic list 2>/dev/null || echo "error")

if echo "$TOPICS" | grep -q "user-logins"; then
    log_success "Redpanda topics created and visible"
else
    log_warn "Topic list returned: '$TOPICS' (expected user-logins, user-logouts)"
fi

echo ""

# =============================================================================
# Consumer Worker
# =============================================================================
log_info "Deploying Consumer worker..."
kubectl apply -f "$K8S_DIR/13-consumer.yaml"

if ! wait_for_deployment_ready "consumer" "portfolio" 60 "Consumer"; then
    log_error "Consumer deployment failed"
    kubectl logs -n portfolio -l app=consumer -c consumer --tail=30 2>/dev/null || true
    exit 1
fi

sleep 5

log_info "Verifying Consumer is connected to Redpanda and Temporal..."
CONSUMER_LOGS=$(kubectl logs -n portfolio -l app=consumer -c consumer --tail=50 2>/dev/null || echo "error")

if echo "$CONSUMER_LOGS" | grep -q "consumer_started" && \
   echo "$CONSUMER_LOGS" | grep -q "temporal_connected"; then
    log_success "Consumer connected to Redpanda and Temporal"
else
    log_warn "Could not confirm consumer startup — check logs:"
    log_warn "  kubectl logs -n portfolio -l app=consumer -c consumer"
fi
echo ""
# =============================================================================
# Backend
# =============================================================================
log_info "Deploying Backend (1 replica)..."
kubectl apply -f "$K8S_DIR/09-backend.yaml"

if ! wait_for_pods_ready "app=backend" "portfolio" 300 "Backend"; then
    log_error "Backend failed"
    kubectl logs -n portfolio -l app=backend -c backend --tail=30 2>/dev/null || true
    exit 1
fi

log_info "Verifying Backend health endpoint..."

BACKEND_POD=$(kubectl get pods -n portfolio -l app=backend -o jsonpath='{.items[0].metadata.name}')
BACKEND_HEALTH=$(kubectl exec -n portfolio "$BACKEND_POD" -c backend -- \
  python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/v1/health').getcode())" \
  2>/dev/null || echo "error")

if [ "$BACKEND_HEALTH" = "200" ]; then
    log_success "Backend healthy (HTTP 200)"
else
    log_warn "Backend health returned: '$BACKEND_HEALTH' (expected 200)"
fi

echo ""
# =============================================================================
# Monitoring (Grafana + Loki + Alloy)
# =============================================================================
log_info "Creating Grafana secrets from password files..."

kubectl create secret generic monitoring-secrets \
  --from-literal=GF_SECURITY_ADMIN_USER=admin \
  --from-literal=GF_SECURITY_ADMIN_PASSWORD="$GRAFANA_ADMIN_PASS" \
  --from-literal=GF_DEMO_PASSWORD="$GRAFANA_DEMO_PASS" \
  -n portfolio \
  --dry-run=client -o yaml | kubectl apply -f -

log_success "monitoring-secrets created"

log_info "Deploying monitoring stack (Grafana + Loki + Alloy)..."

# Delete previous init Job if it exists — Jobs are immutable, apply fails if it already exists.
kubectl delete job grafana-init-users -n portfolio 2>/dev/null || true

kubectl apply -f "$K8S_DIR/17-monitoring.yaml"

if ! wait_for_pods_ready "app=grafana" "portfolio" 120 "Grafana"; then
    log_error "Grafana failed"
    kubectl logs -n portfolio -l app=grafana -c grafana --tail=30 2>/dev/null || true
    exit 1
fi

log_info "Verifying Grafana health..."
GRAFANA_POD=$(kubectl get pods -n portfolio -l app=grafana -o jsonpath='{.items[0].metadata.name}')
GRAFANA_HEALTH=$(kubectl exec -n portfolio "$GRAFANA_POD" -c grafana -- \
  wget -qO- http://localhost:3000/api/health 2>/dev/null || echo "error")

if echo "$GRAFANA_HEALTH" | tr -d ' \n' | grep -q '"database":"ok"'; then
    log_success "Grafana healthy (database ok)"
else
    log_warn "Grafana health returned: '$GRAFANA_HEALTH'"
fi

# =============================================================================
# Grafana User Init (creates demo Viewer user)
# Job is defined at the bottom of 17-monitoring.yaml — already applied above.
# =============================================================================
log_info "Waiting for Grafana user init Job..."

if ! kubectl wait --for=condition=complete job/grafana-init-users -n portfolio --timeout=120s; then
    log_error "Grafana user init Job failed"
    kubectl logs -n portfolio -l job-name=grafana-init-users --tail=30 2>/dev/null || true
    log_warn "Grafana is up but demo user may not have been created"
    log_warn "Re-run manually:"
    log_warn "  kubectl delete job grafana-init-users -n portfolio"
    log_warn "  kubectl apply -f k8s/17-monitoring.yaml"
else
    log_success "Grafana users initialized"
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

# /health is defined on the HTTPS server block (443) only — the HTTP block (80)
# only handles ACME challenges and redirects everything else.
# wget inside the pod fails because it refuses the self-signed cert even with
# --no-check-certificate when connecting to localhost.
# curl -sk works: -s silences progress, -k skips cert verification.
# We hit localhost directly on the droplet because nginx is the only ingress
# point — it terminates TLS for the entire cluster, so it's always reachable
# at the droplet's loopback address on 443.
NGINX_HEALTH=$(curl -sk https://localhost/health 2>/dev/null || echo "error")

if echo "$NGINX_HEALTH" | grep -q "healthy"; then
    log_success "Nginx healthy"
else
    log_warn "Nginx health returned: '$NGINX_HEALTH'"
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
echo "  Frontend: https://testproveoportfolio.xyz/front-page/front-page.html"
echo "  Grafana:  https://testproveoportfolio.xyz/grafana"
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
echo "     kubectl exec -n portfolio postgres-primary-0 -c postgres -- \\"
echo "       psql -U postgres -d portfolio -c \\"
echo "       'SELECT client_addr, state FROM pg_stat_replication;'"
echo ""
echo "  5. Access Temporal UI (port-forward):"
echo "     kubectl port-forward -n portfolio svc/temporal-ui 8080:8080"
echo "     # Then open http://localhost:8080 via SSH tunnel"
echo ""
echo "  6. Monitor memory:"
echo "     watch 'free -h && echo && kubectl top pods -n portfolio'"
echo ""
echo "  7. Grafana demo user password:"
echo "     cat ${GRAFANA_DEMO_PASS_FILE}"
echo "     # Add this to the README once confirmed working"
echo ""
echo "  Credentials: ${SCRIPT_DIR}/.credentials"
echo ""
echo "============================================"
echo "  MEMORY BUDGET (4GB droplet + 2GB swap)"
echo "============================================"
echo ""
echo "  k3s system:         ~300MB"
echo "  PostgreSQL primary:   ~83Mi actual"
echo "  PostgreSQL replica:   ~49Mi actual"
echo "  Redis:                 ~6Mi actual"
echo "  MinIO:                ~86Mi actual"
echo "  Image Service:       ~367Mi actual (TensorFlow NSFW)"
echo "  Backend:              ~75Mi actual"
echo "  Nginx:                 ~4Mi actual"
echo "  Redpanda:            ~300Mi actual"
echo "  Consumer:             ~25Mi actual"
echo "  Temporal server:      ~91Mi actual"
echo "  Temporal UI:           ~7Mi actual"
echo "  Temporal worker:      ~50Mi actual"
echo "  LibreTranslate:      ~560Mi actual (en+es models warm)"
echo "  Loki:                 ~58Mi actual"
echo "  Alloy:                ~45Mi actual"
echo "  Grafana:              ~86Mi actual"
echo "  ─────────────────────────────────"
echo "  Total pod actual:   ~1892Mi"
echo "  Node used:           ~3.2Gi (includes k3s, kernel, buff/cache)"
echo "  Available:            4096MB RAM + 2048MB swap"