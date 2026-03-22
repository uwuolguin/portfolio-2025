# Portfolio K8s - DigitalOcean Droplet Deployment

A Kubernetes (k3s) deployment showcasing:
- **PostgreSQL Primary + Read Replica**: Demonstrates database replication
- **Image Service with NSFW Detection**: TensorFlow-based content moderation
- **Redpanda Event Streaming**: Kafka-compatible broker with explicit partition routing
- **Consumer Worker**: Redpanda consumer that routes events to Temporal by language partition
- **Temporal**: Durable workflow execution: AuthEventWorkflow -> SendNotificationWorkflow (fire and forget child workflow)
- **Full stack on a 4GB droplet**: All features enabled, no compromises

---

## Droplet Specs

- **Plan**: Premium AMD ~$28/mo
- **RAM**: 4 GB + 2 GB swap
- **CPU**: 2 AMD vCPUs
- **Disk**: 60 GB NVMe SSD
- **Region**: SFO3
- **OS**: Ubuntu 24.04 (LTS) x64

---

## User Setup

All scripts run as a **regular user with sudo privileges**, never as root directly.

```bash
# If you only have root, create a user first:
adduser deploy
usermod -aG sudo deploy
su - deploy
```

---

## Quick Start

### 1. Create Droplet and SSH In
```bash
ssh deploy@<your-droplet-ip>
```

### 2. Clone Repo
```bash
git clone https://github.com/uwuolguin/portfolio-2025.git
cd portfolio-2025
```

### 3. Install k3s + Docker
```bash
cd "k8s scripts"
chmod +x *.sh
./00-install-k3s.sh

# After install, activate docker group:
newgrp docker
```

### 4. Build Images on Droplet
```bash
./build-and-import-k3s.sh
```
> This takes 10-20 min. The image-service (TensorFlow wheels) is the slowest.

### 4.5. Set API Keys and Passwords

**Resend (email):**
```bash
./set-resend-key.sh
```

**Grafana passwords (required before deploy):**
```bash
# Files live in k8s scripts/ alongside .env.secrets and .credentials
echo "your-strong-admin-password" > .grafana-admin-password
echo "your-demo-password"         > .grafana-demo-password
chmod 600 .grafana-admin-password .grafana-demo-password
```

Both files are static. Set them once, they never change. The deploy script reads them and puts them into `monitoring-secrets`. If k3s is wiped and redeployed, the files are still on the droplet and the passwords stay the same.

### 5. Deploy
```bash
./deploy-k3s-local.sh
```

The script handles everything in order: reads the password files, creates `monitoring-secrets`, deploys Grafana, waits for it to be healthy, then runs `17-grafana-init-users.yaml` as a one-shot Job that creates the demo Viewer user via the Grafana HTTP API. Admin is created automatically by Grafana from the secret env vars.

After deploy the script prints:
```
7. Grafana demo user password:
   cat .grafana-demo-password
   # Add this to the README once confirmed working
```

### 7. Post-Deploy
```bash
# Create admin user
kubectl exec -it -n portfolio deployment/backend -- \
  python -m scripts.admin.create_admin

# Seed test data (optional)
kubectl exec -n portfolio deployment/backend -- \
  python -m scripts.database.seed_test_data

# Setup pg_cron for search refresh
kubectl exec -n portfolio deployment/backend -- \
  python -m scripts.database.manage_search_refresh_cron

# Run tests
kubectl exec -n portfolio deployment/backend -- \
  pytest app/tests/ -v

# Temporal Logging Verification
# Run test workflows to verify all Temporal log sources are emitting JSON.
# Each workflow targets a different log path:
#   TestSdkLogsWorkflow            -> _SdkJsonFormatter  (temporalio.* Python-side logs)
#   TestAsyncExceptionWorkflow     -> install_async_exception_handler (asyncio loop handler)
#   test_sync_exception_standalone -> sys.excepthook (process-level startup crash)
#   TestCoreLogsWorkflow           -> _CoreJsonFormatter (Rust core via LogForwardingConfig)
#
# Step 1 - open a second terminal and tail the worker logs BEFORE triggering:
kubectl logs -n portfolio deployment/temporal-worker -f
#
# Step 2 - in this terminal, trigger all four workflows:
kubectl exec -n portfolio deployment/backend -- \
  python -m app.temporal.workflows.test_sync_exception_standalone

kubectl exec -n portfolio deployment/backend -- \
  python -m app.temporal.trigger_test_workflows
#
# What to look for in the worker logs:
#
#   SDK log (Python-side):
#   {"timestamp":"...","level":"warning","logger":"temporalio.workflow","event":"test_workflow_sdk_log..."}
#
#   Async exception:
#   {"level":"error","event":"uncaught_async_exception","exc_info":"...RuntimeError: test async..."}
#
#   Sync exception (run separately - crashes the process by design):
#   {"level": "critical", "event": "sync_uncaught_exception", "exc_info": "...RuntimeError..."}
#
#   Core log (Rust):
#   {"level":"warn","logger":"temporalio.core...","event":"..."}
#   (appears after TestCoreLogsWorkflow times out its activity - wait ~5 seconds)
#
# To filter by log type:
kubectl logs -n portfolio deployment/temporal-worker | grep '"logger":"temporalio'
kubectl logs -n portfolio deployment/temporal-worker | grep '"event":"uncaught_async'
kubectl logs -n portfolio deployment/temporal-worker | grep '"event":"uncaught_sync\|thread'
kubectl logs -n portfolio deployment/temporal-worker | grep '"logger":"temporalio.core'
```

### 8. Access
```
https://testproveoportfolio.xyz/front-page/front-page.html
https://testproveoportfolio.xyz/docs
https://testproveoportfolio.xyz/health
```

---

## Grafana Credentials

Two users, two files, both static.

### Password Files

| File | User | Role |
|------|------|------|
| `.grafana-admin-password` | `admin` | Admin - full access |
| `.grafana-demo-password` | `demo` | Viewer - dashboards only |

Both live in `k8s scripts/` alongside `.env.secrets` and `.credentials`. Both are `chmod 600` and git-ignored. Both are static: set them once before first deploy, never touch them again.

If k3s is wiped and redeployed (`./cleanup.sh` + `./deploy-k3s-local.sh`), the files remain on the droplet and the passwords stay the same.

### How Users Get Created

**Admin** is created automatically by Grafana on startup from the `GF_SECURITY_ADMIN_USER` and `GF_SECURITY_ADMIN_PASSWORD` env vars in `monitoring-secrets`. No action needed.

**Demo** (Viewer) is created by `17-grafana-init-users.yaml`, a one-shot Job that runs as part of deploy after Grafana is confirmed healthy. The Job calls the Grafana HTTP API to create the user and set the Viewer role. Idempotent: if the user already exists on redeploy, it updates the password to match the file.

### Re-run User Init Manually

```bash
kubectl delete job grafana-init-users -n portfolio
kubectl apply -f k8s/17-grafana-init-users.yaml
kubectl wait --for=condition=complete job/grafana-init-users -n portfolio --timeout=120s
kubectl logs -n portfolio -l job-name=grafana-init-users
```

### Access Grafana

```bash
# Port-forward on the droplet:
kubectl port-forward -n portfolio svc/grafana 3000:3000

# SSH tunnel from your laptop:
ssh -L 3000:localhost:3000 deploy@<droplet-ip>

# Open: http://localhost:3000
# Admin: admin / <contents of .grafana-admin-password>
# Demo:  demo  / <contents of .grafana-demo-password>
```

---

## What Needs sudo vs What Doesn't

| Command | sudo needed? | Why |
|---------|-------------|-----|
| `kubectl ...` | **No** | kubeconfig copied to ~/.kube/config |
| `docker build` | **No** | user added to docker group |
| `sudo k3s ctr images import` | **Yes** | k3s containerd is root-owned |
| Swap/sysctl/apt | **Yes** | system-level operations |

---

## What This Demonstrates

### 1. PostgreSQL Replication

- **Primary (writes)**: All INSERT/UPDATE/DELETE operations
- **Replica (reads)**: All SELECT queries (with fallback to primary)
- Automatic streaming replication with WAL

> **Schema note**: All application tables live in the `proveo` schema (not `public`).
> Use `\dt proveo.*` to list tables and `SET search_path TO proveo;` to avoid typing the schema prefix.
> `alembic_version` is the only table in `public`.

```bash
# Verify replication is working
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT application_name, state, sync_state FROM pg_stat_replication;"'
```

### 2. Confirm Replica is in Recovery Mode

```bash
POSTGRES_PASS=$(kubectl get secret portfolio-secrets -n portfolio \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)

kubectl exec -n portfolio postgres-replica-0 -- \
  bash -c "PGPASSWORD='${POSTGRES_PASS}' psql -U postgres -d postgres \
  -c 'SELECT pg_is_in_recovery();'"
# Should return: t (true)
```

### 3. Image Service with NSFW Detection

```bash
# Check NSFW model status
kubectl logs -n portfolio deployment/image-service | grep -i "nsfw\|model\|loaded"

# Check health endpoint
kubectl port-forward -n portfolio svc/image-service 8080:8080 &
sleep 2
curl http://localhost:8080/health
# Expected: {"status":"healthy",...,"nsfw":{"enabled":true,"model_loaded":true,...}}
```

### 4. Redpanda Event Streaming

```bash
# Verify broker is healthy
kubectl exec -n portfolio redpanda-0 -- \
  rpk cluster health --api-urls=localhost:9644
# Expected: HEALTHY: true, Controller: redpanda-0

# List topics
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic list --brokers=localhost:9092
# Expected:
#   NAME           PARTITIONS  REPLICAS
#   user-logins    2           1
#   user-logouts   2           1

# Watch events arrive in real time - trigger a login in another terminal
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic consume user-logins --brokers=localhost:9092 --num=5
# partition 0 = es users, partition 1 = en users

# Check message count per partition
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic describe user-logins --print-watermarks --brokers=localhost:9092

# Verify producer connected
kubectl logs -n portfolio deployment/backend | grep "kafka_producer_started"

# Verify events are being published
kubectl logs -n portfolio deployment/backend | grep "kafka_event_published"

# Check for producer failures (should be empty)
kubectl logs -n portfolio deployment/backend | grep "kafka_event_failed\|kafka_event_skipped"
```

### 5. Consumer Worker

```bash
# Verify consumer is running
kubectl get pods -n portfolio -l app=consumer

# Check consumer connected to Redpanda
kubectl logs -n portfolio deployment/consumer | grep "consumer_started"

# Watch workflow routing in real time
kubectl logs -n portfolio deployment/consumer -f | \
  grep "workflow_started\|workflow_duplicate_skipped\|workflow_start_failed"
# Expected on login:
# {"event":"workflow_started","workflow_id":"auth-user-logins-0-3","workflow":"AuthEventWorkflow",...}

# Check Temporal connection status
kubectl logs -n portfolio deployment/consumer | grep "temporal_connected"

# Check committed offsets
kubectl exec -n portfolio redpanda-0 -- \
  rpk group describe auth-event-workers --brokers=localhost:9092
# CURRENT-OFFSET vs LOG-END-OFFSET - gap = messages not yet processed
```

### 6. Temporal - Durable Workflow Execution

The full event pipeline:

```
Login/Logout -> Redpanda -> Consumer -> Temporal (auth-queue)
  -> AuthEventWorkflow
      -> log_event_activity        (structured JSON log of full event)
      -> start_child_workflow      (fire and forget, ABANDON policy)
          -> SendNotificationWorkflow
              -> send_mock_email_activity  (logs what WOULD be sent)
```

The child workflow runs independently. Even if the parent completes or crashes,
`SendNotificationWorkflow` continues to completion.
Source: https://docs.temporal.io/develop/python/child-workflows

```bash
# Verify Temporal server is running
kubectl get pods -n portfolio -l app=temporal
# Expected: temporal-xxxx   1/1   Running

# Verify Temporal worker is running and polling
kubectl get pods -n portfolio -l app=temporal-worker
# Expected: temporal-worker-xxxx   1/1   Running

# Check worker connected and is polling auth-queue
kubectl logs -n portfolio deployment/temporal-worker | grep "temporal_worker_polling"
# Expected: {"event":"temporal_worker_polling","task_queue":"auth-queue",...}

# Watch workflows being executed in real time
# Trigger a login in another terminal while this is running
kubectl logs -n portfolio deployment/temporal-worker -f | \
  grep "auth_event_received\|mock_email_sent\|temporal_worker"

# Verify parent workflow ran (log_event_activity output)
kubectl logs -n portfolio deployment/temporal-worker | grep "auth_event_received"
# Expected: {"event":"auth_event_received","workflow_id":"auth-user-logins-0-3",
#            "event_type":"login","lang":"en","email":"user@example.com",...}

# Verify child workflow ran (send_mock_email_activity output)
kubectl logs -n portfolio deployment/temporal-worker | grep "mock_email_sent"
# Expected: {"event":"mock_email_sent","to":"user@example.com",
#            "event_type":"login","lang":"en","note":"MOCK - no real email sent",...}

# Access Temporal UI via port-forward
#
# Port-forward creates a direct tunnel to the pod, bypassing nginx entirely.
# We use port 8888 to avoid conflicts with other local services (e.g. EDB Postgres).
#
# Full chain:
#   your browser :8888 -> SSH -> droplet localhost:8888 -> kubectl -> temporal-ui pod:8080
#
# Step 1 - on the droplet:
kubectl port-forward -n portfolio svc/temporal-ui 8888:8080

# Step 2 - on your laptop (SSH tunnel):
ssh -L 8888:localhost:8888 deploy@143.110.154.54

# Step 3 - open in browser:
# http://localhost:8888

# Verify Temporal databases were created by auto-setup
POSTGRES_PASS=$(kubectl get secret portfolio-secrets -n portfolio \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
kubectl exec -n portfolio postgres-primary-0 -- \
  bash -c "PGPASSWORD='${POSTGRES_PASS}' psql -U postgres -c '\l'" | grep temporal
# Expected: temporal and temporal_visibility databases listed
```

---

## Common Commands

### View Running Services and Memory Usage

```bash
# Per-pod actual memory and CPU usage
kubectl top pods -n portfolio

# Node-level RAM overview
free -h

# Both together, refreshing every 2 seconds
watch 'echo "=== NODE ===" && free -h && echo "" && \
  echo "=== PODS ===" && kubectl top pods -n portfolio 2>/dev/null'

# All pods with node assignment
kubectl get pods -n portfolio -o wide
```

### Check Database Activity

```bash
# Connect to primary
kubectl exec -it -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio'

# Once inside psql:
#   \dt proveo.*                  -- list all tables
#   SET search_path TO proveo;    -- avoid typing proveo. every time

# Connect to replica (reads only)
POSTGRES_PASS=$(kubectl get secret portfolio-secrets -n portfolio \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
kubectl exec -it -n portfolio -c postgres postgres-replica-0 -- \
  bash -c "PGPASSWORD='${POSTGRES_PASS}' psql -U postgres -d portfolio"

# Check replication lag
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT client_addr, state, replay_lag FROM pg_stat_replication;"'

# Quick table counts
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT schemaname, tablename, n_live_tup FROM pg_stat_user_tables \
  WHERE schemaname = '"'"'proveo'"'"' ORDER BY n_live_tup DESC;"'
```

### Check Redpanda Activity

```bash
kubectl exec -n portfolio redpanda-0 -- \
  rpk cluster health --api-urls=localhost:9644

kubectl exec -n portfolio redpanda-0 -- \
  rpk topic list --brokers=localhost:9092

kubectl exec -n portfolio redpanda-0 -- \
  rpk topic consume user-logins --brokers=localhost:9092 --num=10

kubectl exec -n portfolio redpanda-0 -- \
  rpk topic describe user-logins --print-watermarks --brokers=localhost:9092
```

### Monitor Logs

```bash
kubectl logs -n portfolio deployment/backend -f
kubectl logs -n portfolio deployment/temporal-worker -f
kubectl logs -n portfolio deployment/consumer -f
kubectl logs -n portfolio deployment/image-service -f
kubectl logs -n portfolio redpanda-0 -f
```

### Access Services via Port-Forward

```bash
# API docs (bypasses nginx - direct tunnel to backend pod)
kubectl port-forward -n portfolio svc/backend 8000:8000

# MinIO console (bypasses nginx - direct tunnel to minio pod)
kubectl port-forward -n portfolio svc/minio 9001:9001

# Temporal UI (bypasses nginx - direct tunnel to temporal-ui pod)
# Uses 8888 to avoid conflict with local services on 8080
kubectl port-forward -n portfolio svc/temporal-ui 8888:8080

# Grafana (bypasses nginx - direct tunnel to grafana pod)
kubectl port-forward -n portfolio svc/grafana 3000:3000
```

---

## Scaling Up

```bash
# Scale backend and image service to 2 replicas
kubectl scale deployment backend -n portfolio --replicas=2
kubectl scale deployment image-service -n portfolio --replicas=2

# Scale Temporal workers - Temporal distributes tasks automatically,
# no partition assignment or leader election needed
kubectl scale deployment temporal-worker -n portfolio --replicas=3

# Scale Redpanda to 3-node cluster
kubectl scale statefulset redpanda -n portfolio --replicas=3
kubectl exec -n portfolio redpanda-0 -- rpk cluster rebalance
```

---

## Troubleshooting

### OOM Kills

```bash
kubectl get events -n portfolio --sort-by=.lastTimestamp | grep -i oom
free -h
kubectl top pods -n portfolio
```

### Pod Won't Start

```bash
kubectl describe pod <pod-name> -n portfolio
kubectl logs <pod-name> -n portfolio
```

### Temporal Worker Not Picking Up Tasks

```bash
# Check worker is polling the right queue
kubectl logs -n portfolio deployment/temporal-worker | grep "temporal_worker_polling"

# Check worker connected to Temporal server
kubectl logs -n portfolio deployment/temporal-worker | grep "temporal_client_connected"

# Check for uncaught exceptions (all logged as JSON)
kubectl logs -n portfolio deployment/temporal-worker | grep "uncaught"

# Verify Temporal server is accepting TCP connections
kubectl exec -n portfolio deployment/temporal-worker -- \
  nc -zv temporal 7233
# Expected: Connection to temporal 7233 port succeeded
```

### Temporal Server Not Starting

```bash
# Check logs - auto-setup migrations take 30-60s on first boot
kubectl logs -n portfolio -l app=temporal --tail=50

# Verify temporal databases exist in PostgreSQL
POSTGRES_PASS=$(kubectl get secret portfolio-secrets -n portfolio \
  -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
kubectl exec -n portfolio postgres-primary-0 -- \
  bash -c "PGPASSWORD='${POSTGRES_PASS}' psql -U postgres -c '\l'" | grep temporal
```

### Replica Not Syncing

```bash
kubectl exec -n portfolio postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT slot_name, active FROM pg_replication_slots;"'

# Recreate replica if needed - StatefulSet will auto-recreate and re-sync
kubectl delete pod -n portfolio postgres-replica-0
```

### Redpanda Not Starting or Topics Missing

```bash
kubectl logs -n portfolio redpanda-0 --tail=50

# Re-run init Job
kubectl delete job redpanda-init -n portfolio 2>/dev/null || true
kubectl apply -f k8s/12-redpanda-init.yaml

kubectl exec -n portfolio redpanda-0 -- \
  rpk topic list --brokers=localhost:9092
```

### kubectl Permission Denied

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
export KUBECONFIG=~/.kube/config
```

### Stale PVC Data After Redeployment

```bash
# If PostgreSQL rejects passwords after a fresh deploy, old data survived cleanup.
# local-path provisioner leaves data on disk even after namespace deletion.
./cleanup.sh
kubectl wait --for=delete namespace/portfolio --timeout=60s
sudo rm -rf /var/lib/rancher/k3s/storage/*
sudo ls /var/lib/rancher/k3s/storage/   # must be empty before proceeding
# delete every image in k3s if needed
sudo k3s ctr images ls -q | sudo xargs -r k3s ctr images rm
./deploy-k3s-local.sh
```

### Clean Restart

```bash
./cleanup.sh
sudo rm -rf /var/lib/rancher/k3s/storage/*
./deploy-k3s-local.sh
```

### Grafana Demo User Not Created

```bash
# Re-run the init Job
kubectl delete job grafana-init-users -n portfolio
kubectl apply -f k8s/17-grafana-init-users.yaml
kubectl wait --for=condition=complete job/grafana-init-users -n portfolio --timeout=120s
kubectl logs -n portfolio -l job-name=grafana-init-users
```

---

## What's in the Manifests

| File | Description |
|------|-------------|
| `00-namespace.yaml` | Creates `portfolio` namespace |
| `01-configmap.yaml` | App configuration |
| `02-secrets.yaml` | Documentation only - secrets auto-generated by deploy script |
| `03-pvcs.yaml` | Persistent storage (5GB PG, 10GB MinIO, 512MB Redis) |
| `04-postgres-primary.yaml` | **Primary database** - writes, replication source |
| `05-postgres-replica.yaml` | **Read replica** - streaming replication |
| `06-redis.yaml` | Cache (64MB maxmemory, LRU eviction) |
| `07-minio.yaml` | Object storage for images |
| `08-image-service.yaml` | **NSFW detection service** - TensorFlow model |
| `09-backend.yaml` | FastAPI app (migrations via initContainer) |
| `10-nginx.yaml` | Reverse proxy, gzip, rate limiting, security headers |
| `11-redpanda.yaml` | **Kafka-compatible event broker** - StatefulSet, persistent storage |
| `12-redpanda-init.yaml` | **One-shot Job** - creates topics after broker is confirmed healthy |
| `13-consumer.yaml` | **Consumer worker** - polls Redpanda, routes events to Temporal |
| `14-temporal.yaml` | **Temporal server + UI** - durable workflow execution, PostgreSQL persistence |
| `15-temporal-worker.yaml` | **Temporal worker** - executes AuthEventWorkflow and SendNotificationWorkflow |
| `16-libretranslate.yaml` | Self-hosted translation service (ES/EN) |
| `17-monitoring.yaml` | **Grafana + Loki + Promtail** - observability stack, all in portfolio namespace |
| `17-grafana-init-users.yaml` | **One-shot Job** - creates Grafana demo Viewer user after Grafana is healthy |

---

## Learning Highlights

1. **StatefulSets**: postgres-primary, postgres-replica, redpanda - stable network identity, ordered startup, per-replica storage
2. **Deployments**: Stateless services (backend, image-service, nginx, temporal, temporal-worker)
3. **Jobs**: One-shot configuration tasks (redpanda-init topic creation)
4. **Services**: ClusterIP for internal communication, LoadBalancer for external access
5. **InitContainers**: Wait for dependencies, run migrations, bootstrap replica from primary
6. **ConfigMaps/Secrets**: Separate config from code, auto-generated credentials
7. **PersistentVolumeClaims**: Data survives pod restarts (volumeClaimTemplates for Redpanda)
8. **Liveness/Readiness Probes**: Auto-healing and traffic gating
9. **Resource Limits**: Memory budgeting for constrained environments
10. **Explicit partition routing**: Bypassing Kafka key hashing with a direct PARTITION_MAP
11. **Deploy ordering**: StatefulSet wait -> Job apply pattern solving the init-container deadlock
12. **Consumer worker**: Manual offset commits, at-least-once delivery, Temporal deduplication via deterministic workflow IDs
13. **Temporal child workflows**: Fire and forget pattern with ABANDON parent close policy - child runs independently after parent completes
14. **TCP vs gRPC probes**: busybox nc for layer 4 TCP readiness check vs grpc_health_probe for layer 7
15. **Structured logging**: Every log line including Temporal SDK internals and uncaught exceptions routed to JSON via structlog
16. **pg_hba mixed auth policy**: Both SSL and non-SSL TCP accepted - encryption enforced at the application layer per service, not globally at the database
17. **Grafana RBAC**: Two-user model with static admin (created from env vars) and Viewer demo user (created by a one-shot init Job via HTTP API), both sourced from files on the droplet that survive k3s wipes

---

## General Notes

- **All features enabled**: NSFW detection, replication, event streaming, Temporal workflows, caching.
- **Self-signed SSL**: PostgreSQL certificates are auto-generated by an initContainer.
- **No external registry**: Custom images are built on-droplet and imported to k3s.
- **Official images**: PostgreSQL, Redis, MinIO, Redpanda, and Temporal pulled from their registries automatically.
- **Auto-generated secrets**: Deploy script creates secure passwords and saves them to `.credentials`.
- **Non-root operation**: Scripts use `sudo` only where needed; `kubectl` runs as a regular user.
- **Schema layout**: All application tables live in the `proveo` schema. `public` only contains `alembic_version`.
- **Node destruction warning**: Data is stored on the node's local SSD via `local-path`. If the node is deleted, data is lost. For production consider scheduled `pg_dump` backups to S3, DigitalOcean Block Storage, or Barman/pgBackRest for continuous WAL archiving.

## Volume / VolumeMount Order (Kubernetes Note)

1. **Volumes (`volumes:`)**: Created before any container starts. Includes PVCs, `emptyDir`, and ConfigMaps.
2. **VolumeMounts**: Per-container mappings. Kubernetes mounts volumes at specified paths before the container starts.
3. **InitContainers**: Run after volumes exist and are mounted. Can write to volumes to prepare data or certificates.
4. **Main containers**: Run after all initContainers complete. See whatever initContainers wrote to the volumes.

## Memory Budget (4GB Droplet)

Actual measurements from `kubectl top pods` on a running cluster, alongside
configured requests/limits. Use `kubectl top pods -n portfolio` to verify on your deployment.

```
Component              Actual     Request    Limit
--------------------------------------------------
k3s system             ~300MB     -          -
postgres-primary        104Mi     192Mi      384Mi
postgres-replica         34Mi     128Mi      256Mi
redis                     4Mi      32Mi       96Mi
minio                    81Mi     128Mi      256Mi
image-service           331Mi     384Mi      768Mi   (TensorFlow NSFW)
backend                  79Mi     192Mi      512Mi
nginx                     4Mi      32Mi      128Mi
redpanda                146Mi     512Mi      768Mi
consumer                 27Mi      64Mi      128Mi
temporal                 85Mi     256Mi      512Mi
temporal-ui               9Mi      64Mi      128Mi
temporal-worker          62Mi     128Mi      256Mi
libretranslate          226Mi     256Mi      512Mi
loki                    128Mi     128Mi      256Mi
promtail                 64Mi      64Mi      128Mi
grafana                 128Mi     128Mi      256Mi
--------------------------------------------------
Current actual total   ~1376Mi
Current node used       ~2.3Gi   (includes k3s overhead, kernel, buff/cache)
--------------------------------------------------
Total requests          ~2768Mi
Total limits            ~5332Mi
Available                4096Mi RAM + 2048Mi swap
```

> The gap between actual pod usage and node used is k3s system
> processes, kernel buffers, and page cache - normal and expected.
> Image service is the heaviest pod at 399Mi actual - TensorFlow keeps the
> model loaded in memory at all times.