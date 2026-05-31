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
# -a      # append — ADD to the existing groups, don't replace them
          # without -a, -G replaces ALL current groups with the new list
          # meaning the user loses every group they were in before
          # -a must always be used with -G, never alone

# -G sudo # the group to add the user to
          # sudo group = members can run commands as root via sudo

# deploy  # the username being modified

# Users, groups, and sudo permissions are part of Linux's filesystem permission
# model — every file and directory has an owner, a group, and rwx (read, write,
# execute) bits that control exactly who can do what. Creating a dedicated deploy
# user instead of running everything as root is the practical application of that
# model — least privilege, each user owns only what they need to touch.
```
### USEFULCOMMANDS.md

See this file "USEFULCOMMANDS.md" for commands to inspect the system at a deeper level — process state, open file descriptors, network connections, auth logs, and the filesystem itself. That's where the juice is. Also includes a security mental model worth a look.
---

## Quick Start

### 0. Set Up SSL / HTTPS

Before deploying, point your domain to this droplet and obtain TLS certificates.
Full walkthrough: **[SSL Setup Guide](./SSL_SETUP.md)**.

### 1. Create Droplet and SSH In
```bash
ssh deploy@<your-droplet-ip>
```

### 2. Clone Repo
```bash
git clone https://github.com/uwuolguin/portfolio-2025.git
# Execute "git pull origin main" to update the repository if already cloned.
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
### 3.5. Allow deploy to Run sudo Without a Password (Required for CI)

The GitHub Actions deploy workflow SSHes in as `deploy` and runs scripts that
call `sudo` internally. This prevents any sudo-related failures in non-interactive SSH sessions.

```bash
# run as root
sudo su -
echo "deploy ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/deploy
chmod 440 /etc/sudoers.d/deploy
exit
```

> This is safe for a single-user personal server where `deploy` is the only
> non-root account. On multi-tenant servers you would scope this to specific
> commands instead of `ALL`.

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
# ls -lb -a command and flags allow you to see all elements in a directory
echo "your-strong-admin-password" > .grafana-admin-password
echo "your-demo-password"         > .grafana-demo-password
chmod 600 .grafana-admin-password .grafana-demo-password
```

Both files are static. Set them once, they never change. The deploy script reads them and puts them into `monitoring-secrets`. If k3s is wiped and redeployed, the files are still on the droplet and the passwords stay the same.

### 5. Deploy
```bash
./deploy-k3s-local.sh
```

The script handles everything in order: reads the password files, creates `monitoring-secrets`, deploys Grafana, waits for it to be healthy, then runs the grafana-init-users Job (embedded in `17-monitoring.yaml`) that creates the demo Viewer user via the Grafana HTTP API. Admin is created automatically by Grafana from the secret env vars.

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

+# Each workflow targets a different log path:
#   TestSdkLogsWorkflow            -> _SdkJsonFormatter  (temporalio.* Python-side logs)
#   TestAsyncExceptionWorkflow     -> install_async_exception_handler (asyncio loop handler)
#   test_sync_exception_standalone -> sys.excepthook (process-level startup crash)
#   TestCoreLogsWorkflow           -> _CoreJsonFormatter (Rust core via LogForwardingConfig)
#
# Step 1 - open a second terminal and tail the worker logs BEFORE triggering:
kubectl logs -n portfolio deployment/temporal-worker -f
#
# Step 2 - in this terminal, trigger all four workflows, sync exceeption separated by desing:
kubectl exec -n portfolio deployment/backend -- \
  python -m app.temporal.workflows.test_sync_exception_standalone

kubectl exec -n portfolio deployment/backend -- \
  python -m app.temporal.trigger_test_workflows

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
kubectl logs -n portfolio deployment/temporal-worker | grep 'temporalio'
kubectl logs -n portfolio deployment/temporal-worker | grep 'uncaught_async'
kubectl logs -n portfolio deployment/temporal-worker | grep 'uncaught_sync'
kubectl logs -n portfolio deployment/temporal-worker | grep 'temporalio.core'
```
### 7.5. Harden the Server

Follow the **SSH Hardening** section in `USEFULCOMMANDS.md` for the full walkthrough.
At minimum, complete these before considering the server production-ready:

- Disable password auth, enable key-only login (`PasswordAuthentication no`)
- Block Kubernetes ports from the public internet via UFW (`6443`, `10250`, `8472`)
- Install `fail2ban` and `unattended-upgrades`

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

**Demo** (Viewer) is created by the `grafana-init-users` Job defined at the bottom of `17-monitoring.yaml`. It runs as part of deploy after Grafana is confirmed healthy, calls the Grafana HTTP API to create the user and set the Viewer role. Idempotent: if the user already exists on redeploy, it updates the password to match the file.

### Re-run User Init Manually

```bash
kubectl delete job grafana-init-users -n portfolio --ignore-not-found
kubectl apply -f k8s/17-monitoring.yaml
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

# See "Accessing Grafana: Network Deep-Dive" at the end of this file for a full explanation of how this works.
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
kubectl port-forward -n portfolio svc/image-service 8080:8080
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
  rpk topic describe user-logins -p --brokers=localhost:9092

# See everything that's NOT a health check
kubectl logs -n portfolio deployment/backend | grep -v "health"

# Check for any Kafka-related activity
kubectl logs -n portfolio deployment/backend | grep -i "kafka\|redpanda\|producer\|consumer\|topic\|publish\|send"

# Check for any errors or warnings
kubectl logs -n portfolio deployment/backend | grep '"level": "error"\|"level": "warn"\|ERROR\|WARN\|Exception\|Traceback'

# See scheduled jobs and non-health events
kubectl logs -n portfolio deployment/backend | grep -v "kube-probe\|health"
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

### 7. Redis

```bash
# Verify Redis is running and accepting connections
kubectl exec -n portfolio deployment/redis -- redis-cli ping
# Expected: PONG

# Check memory usage vs configured 64MB cap
kubectl exec -n portfolio deployment/redis -- redis-cli info memory | grep -E "used_memory_human|maxmemory_human"
# Expected: used_memory_human: ~4M, maxmemory_human: 64.00M

# Check eviction policy (should be allkeys-lru)
kubectl exec -n portfolio deployment/redis -- redis-cli config get maxmemory-policy
# Expected: allkeys-lru
```

### 8. MinIO

```bash
# Check MinIO health
kubectl port-forward -n portfolio svc/minio 9000:9000 &
sleep 2
curl http://localhost:9000/minio/health/ready
# Expected: HTTP 200

# Access MinIO console (browser UI)
kubectl port-forward -n portfolio svc/minio 9001:9001
# Then open http://localhost:9001 via SSH tunnel
ssh -L 9001:localhost:9001 deploy@143.110.154.54
# Credentials: minioadmin / <MINIO_PASSWORD from .credentials>

# Verify images bucket exists
kubectl logs -n portfolio deployment/image-service
```

### 9. LibreTranslate

```bash
# Check service is healthy — first boot takes 2-3 min to download models
kubectl get pods -n portfolio -l app=libretranslate
# STATUS: Running means models are loaded and /health passes

# Check startup progress (model download on first boot)
kubectl logs -n portfolio deployment/libretranslate -f
# Look for: "Loaded" or "Listening at: http://0.0.0.0:5000"

# Test a translation directly inside the cluster
kubectl port-forward -n portfolio svc/libretranslate 5000:5000
#Inside the droplet, in another terminal
curl -s -X POST http://localhost:5000/translate \
  -H "Content-Type: application/json" \
  -d '{"q":"hello","source":"en","target":"es","format":"text"}'
# Expected: {"translatedText":"hola"}

# Test the reverse
kubectl port-forward -n portfolio svc/libretranslate 5000:5000
#Inside the droplet, in another terminal
curl -s -X POST http://localhost:5000/translate \
  -H "Content-Type: application/json" \
  -d '{"q":"hola","source":"es","target":"en","format":"text"}'
# Expected: {"translatedText":"hello"}

# List available language pairs through port-forwarding
kubectl port-forward -n portfolio svc/libretranslate 5000:5000

# Inside the droplet, in another terminal
curl -s http://localhost:5000/languages | python3 -m json.tool

# Expected: only "en" and "es" language entries
# because LT_LOAD_ONLY=en,es
```

### 10. Grafana + Loki + Alloy

```bash
# Verify all three pods are running
kubectl get pods -n portfolio -l app=grafana
kubectl get pods -n portfolio -l app=loki
kubectl get pods -n portfolio -l app=alloy

# Check Loki is ready to receive logs
kubectl port-forward -n portfolio svc/loki 3100:3100 &
sleep 2
curl http://localhost:3100/ready
# Expected: ready

# Check Loki has received logs (query last 5 minutes)
curl -s "http://localhost:3100/loki/api/v1/query_range"   --data-urlencode 'query={app="temporal-worker"}'   --data-urlencode 'limit=5' | python3 -m json.tool | grep '"values"'
# Expected: array of log lines if temporal-worker has been active

# Check Alloy is scraping the temporal-worker pod
kubectl logs -n portfolio -l app=alloy | grep -i "temporal\|loki\|error"

# Access Grafana publicly (no port-forward needed)
# https://testproveoportfolio.xyz/grafana/
# Admin:  admin / <contents of .grafana-admin-password>
# Demo:   demo  / password

# Or via port-forward:
kubectl port-forward -n portfolio svc/grafana 3000:3000
# SSH tunnel from laptop: ssh -L 3000:localhost:3000 deploy@<droplet-ip>
# Open: http://localhost:3000
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
kubectl exec -n portfolio -c postgres postgres-primary-0 --   bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT schemaname,relname, n_live_tup FROM pg_stat_user_tables \
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
  rpk topic describe user-logins --brokers=localhost:9092
```

### Monitor Logs

```bash
kubectl logs -n portfolio deployment/backend -f
kubectl logs -n portfolio deployment/temporal-worker -f
kubectl logs -n portfolio deployment/consumer -f
kubectl logs -n portfolio deployment/image-service -f
kubectl logs -n portfolio deployment/libretranslate -f
kubectl logs -n portfolio redpanda-0 -f
kubectl logs -n portfolio -l app=loki -f
kubectl logs -n portfolio -l app=alloy -f
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

# LibreTranslate (bypasses nginx - direct tunnel to libretranslate pod)
kubectl port-forward -n portfolio svc/libretranslate 5000:5000
# Test: curl -X POST http://localhost:5000/translate -H "Content-Type: application/json" #         -d '{"q":"hello","source":"en","target":"es","format":"text"}'

# Loki (bypasses nginx - direct tunnel to loki pod)
kubectl port-forward -n portfolio svc/loki 3100:3100
# Test: curl http://localhost:3100/ready
```

---

## Horizontal Scaling Plan (not yet tested)

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

### Services That Cannot Be Horizontally Scaled in This Setup

| Service | Why |
|---------|-----|
| `redis` | ReadWriteOnce PVC — only one pod can mount it. Horizontal scaling requires Redis Cluster mode + ReadWriteMany storage |
| `minio` | ReadWriteOnce PVC — only one pod can mount it. Horizontal scaling requires MinIO distributed mode across separate PVCs |
| `libretranslate` | ReadWriteOnce PVC for model cache — only one pod can mount it. Multiple pods would each need their own PVC and re-download models |
| `loki` | StatefulSet with ReadWriteOnce PVC — single-node mode by design. Scaling requires Loki distributed mode |
| `grafana` | ReadWriteOnce PVC for its SQLite database — multiple pods would conflict on the same DB file |

All five use `strategy: Recreate` (or StatefulSet rolling) rather than `RollingUpdate` precisely
because of the RWO PVC constraint — new pod cannot start until old pod releases the mount.

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
#kubectl describe pod nginx-57c77d76b5-t6qj5 -n portfolio
#kubectl logs nginx-57c77d76b5-t6qj5 -n portfolio
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
kubectl port-forward -n portfolio svc/temporal 7233:7233

# Inside the droplet, in another terminal
nc -zv localhost 7233

# Expected: Connection to localhost 7233 port succeeded
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

### LibreTranslate Not Starting or Slow to Start

```bash
# First boot downloads en+es language models (~200MB) — this takes 2-3 minutes
# The startupProbe blocks traffic for up to 240s (24 x 10s) to allow for this
kubectl logs -n portfolio deployment/libretranslate -f
# Look for: "Running on http://0.0.0.0:5000" to confirm models are loaded

# If it stays in ContainerCreating or CrashLoopBackOff:
kubectl describe pod -n portfolio -l app=libretranslate

# PVC permission issue — fix-permissions initContainer should handle this,
# but if the chown failed for any reason:
kubectl exec -n portfolio deployment/libretranslate -- ls -la   /home/libretranslate/.local/share/argos-translate
# Everything should be owned by UID 1032

# Force restart to re-run fix-permissions initContainer
kubectl rollout restart deployment/libretranslate -n portfolio
```

### Image Service Model Not Loading

```bash
# TensorFlow NSFW model loads on startup — takes ~30s after container starts
# Health endpoint returns unhealthy until model is loaded
kubectl logs -n portfolio deployment/image-service -f
# Look for: "model_loaded: true" or "NSFW model loaded"

# If model never loads and pod keeps restarting, it is likely OOM
# The TensorFlow model requires ~500MB — check for eviction
kubectl get events -n portfolio --sort-by=.lastTimestamp | grep -i "image-service\|oom\|evict"
free -h
# If swap is exhausted and RAM is full, other pods may need to be scaled down first

# Check health endpoint directly
kubectl port-forward -n portfolio svc/image-service 8080:8080 &
sleep 2
curl http://localhost:8080/health
# nsfw.model_loaded should be true before the service accepts image uploads
```

### Redis Not Starting

```bash
kubectl logs -n portfolio deployment/redis --tail=30

# Redis uses Recreate strategy because of the RWO PVC.
# If it gets stuck in Terminating during a redeploy, the old pod
# is holding the PVC mount — wait for it to fully terminate.
kubectl get pods -n portfolio -l app=redis -w
# Wait until old pod is gone before new one can mount the PVC
```

### MinIO Not Starting

```bash
kubectl logs -n portfolio deployment/minio --tail=30

# Same RWO PVC issue as Redis — Recreate strategy means old pod must
# die before new pod can mount minio-data.
kubectl get pods -n portfolio -l app=minio -w

# If bucket is missing after restart (should not happen — data persists on PVC):
kubectl logs -n portfolio deployment/image-service | grep -i "bucket\|does not exist"
# Image service creates the bucket on startup if it does not exist
```

### Loki Not Receiving Logs

```bash
# Check Loki is ready
kubectl logs -n portfolio -l app=loki --tail=30

# Check Alloy is running and not erroring
kubectl logs -n portfolio -l app=alloy --tail=30
# Look for connection errors to Loki or permission errors on pod log access

# Verify Alloy has ClusterRole permissions
kubectl get clusterrolebinding alloy -o yaml | grep -A5 "subjects"

# Alloy only scrapes temporal-worker pods — confirm the pod label matches
kubectl get pods -n portfolio -l app=temporal-worker --show-labels
# Must have: app=temporal-worker

# Re-apply monitoring stack to reset Alloy config
kubectl rollout restart daemonset/alloy -n portfolio
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
kubectl apply -f k8s/17-monitoring.yaml
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
| `03-pvcs.yaml` | Persistent storage (5GB PG primary + replica, 10GB MinIO, 512MB Redis, 1GB LibreTranslate) |
| `04-postgres-primary.yaml` | **Primary database** - writes, pg_cron, WAL streaming source |
| `05-postgres-replica.yaml` | **Read replica** - streaming replication, hot standby |
| `06-redis.yaml` | Cache (64MB maxmemory, LRU eviction) |
| `07-minio.yaml` | Object storage for images |
| `08-image-service.yaml` | **NSFW detection service** - TensorFlow model |
| `09-backend.yaml` | FastAPI app (migrations via initContainer) |
| `10-nginx.yaml` | Reverse proxy, TLS termination, gzip, rate limiting, security headers |
| `11-redpanda.yaml` | **Kafka-compatible event broker** - StatefulSet, persistent storage |
| `12-redpanda-init.yaml` | **One-shot Job** - creates topics after broker is confirmed healthy |
| `13-consumer.yaml` | **Consumer worker** - polls Redpanda, routes events to Temporal |
| `14-temporal.yaml` | **Temporal server + UI** - durable workflow execution, PostgreSQL persistence |
| `15-temporal-worker.yaml` | **Temporal worker** - executes AuthEventWorkflow and SendNotificationWorkflow |
| `16-libretranslate.yaml` | Self-hosted translation service (ES/EN only, ~196Mi RAM) |
| `17-monitoring.yaml` | **Grafana + Loki + Alloy** - observability stack + Grafana user init Job |

---

## Learning Highlights

1. **StatefulSets**: postgres-primary, postgres-replica, redpanda - stable network identity, ordered startup, per-replica storage
2. **Deployments**: Stateless services (backend, image-service, nginx, temporal, temporal-worker)
3. **Jobs**: One-shot configuration tasks (redpanda-init topic creation, grafana-init-users)
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
18. **Recreate vs RollingUpdate**: Deployments with ReadWriteOnce PVCs use Recreate strategy to avoid mount deadlocks — old pod releases the PVC before the new one starts

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

1. **Volumes (`volumes:`)**: Declared in the pod spec. PVCs already exist (created by `03-pvcs.yaml`), emptyDir is provisioned fresh by Kubernetes when the pod is scheduled.
2. **VolumeMounts**: Per-container mappings. Kubernetes mounts volumes at specified paths before the container starts.
3. **InitContainers**: Run after volumes are mounted. Can write to volumes to prepare data or certificates.
4. **Main containers**: Run after all initContainers complete. See whatever initContainers wrote to the volumes.

## Memory Budget (4GB Droplet)

Actual measurements from `kubectl top pods` on a running cluster, alongside
configured requests/limits from the manifests. Use `kubectl top pods -n portfolio`
to verify on your deployment.

```
    Component              Actual     Request    Limit
    --------------------------------------------------
    k3s system             ~300MB     -          -
    postgres-primary         83Mi     192Mi      384Mi
    postgres-replica         49Mi     128Mi      256Mi
    redis                     6Mi      32Mi       96Mi
    minio                    86Mi     128Mi      256Mi
    image-service           367Mi     384Mi      768Mi   (TensorFlow NSFW)
    backend                  75Mi     192Mi      512Mi
    nginx                     4Mi      32Mi      128Mi
    redpanda                300Mi     512Mi      768Mi
    consumer                 25Mi      64Mi      128Mi
    temporal                 91Mi     256Mi      512Mi
    temporal-ui               7Mi      64Mi      128Mi
    temporal-worker          50Mi     128Mi      256Mi
    libretranslate          560Mi     400Mi     1000Mi   (en+es models warm, both directions)
    loki                     58Mi     128Mi      256Mi
    alloy                    45Mi      64Mi      128Mi   (replaced Promtail, EOL March 2026)
    grafana                  86Mi     128Mi      256Mi
    --------------------------------------------------
    Current actual total   ~1892Mi
    Current node used        ~3.2Gi  (includes k3s overhead, kernel, buff/cache)
    --------------------------------------------------
    Total requests          ~2836Mi
    Total limits            ~5832Mi
    Available                4096Mi RAM + 2048Mi swap
```

> The gap between actual pod usage (~1892Mi) and node used (~3.2Gi) is not
> a contradiction — pod memory is what the processes inside containers are
> actively using. Node memory includes everything else: the k3s agent, the
> Linux kernel, filesystem page cache, and kernel buffers. Those live outside
> any pod but still consume RAM on the same machine.
> libretranslate is currently the heaviest pod at ~560Mi with both en→es and
> es→en models warm. Cold (models not yet loaded) it sits around ~60Mi.
> `free` is literally unused RAM — nothing touching it.
> `available` is free + whatever the kernel can reclaim on demand, mostly
> buff/cache. The kernel uses spare RAM to cache disk reads but gives it
> back instantly if a process needs it. So `available` is the realistic
> number of how much a new process could actually get.
> In this cluster: 117Mi truly free, 635Mi effectively usable.
> buff/cache (887Mi) is file contents and filesystem metadata the kernel
> cached in RAM to avoid hitting disk twice. It is not locked — the kernel
> evicts it silently the moment any process needs the memory.
---

## 🌐 Linux Networking Fundamentals — Read This First

Everything in the Grafana tunneling section flows from these primitives.
If the port-forward explanation feels like alien text, start here.

// ─── POINTERS, BUFFERS, AND MEMORY — FROM HARDWARE TO USERSPACE ──────────────
//
// AT THE HARDWARE LEVEL
//
// RAM is a giant array of bytes. Every byte has a physical address — a number
// that corresponds to a real location on the physical RAM chip:
//
//     address 0x00000000 → byte 1 on the chip
//     address 0x00000001 → byte 2 on the chip
//     address 0x7fff1234 → byte at that physical location
//     ...billions more
//
// The CPU has a special register called the memory bus. To read or write memory
// the CPU puts an address on the bus, the RAM chip responds with the byte at
// that address. That's it. Hardware is just: address in → byte out.
//
// ─────────────────────────────────────────────────────────────────────────────
//
// WHAT A POINTER ACTUALLY IS
//
// A pointer is just a variable that holds a memory address — a number.
// Nothing magic. Just a number that means "look at this location in RAM":
//
//     int x = 42;           // allocate 4 bytes somewhere in RAM, store 42 there
//     int *p = &x;          // p holds the ADDRESS of x, e.g. 0x7fff1234
//                           // p itself is just a number: 0x7fff1234
//
//     *p                    // "go to address 0x7fff1234, read the bytes there"
//                           // returns 42
//
//     *p = 99;              // "go to address 0x7fff1234, write 99 there"
//                           // x is now 99
//
// The * operator means "follow this address and read/write what's there".
// The & operator means "give me the address of this variable".
//
// ─────────────────────────────────────────────────────────────────────────────
//
// WHAT A BUFFER IS
//
// A buffer is just a contiguous region of memory — multiple bytes in a row —
// used as a temporary holding area for data in transit:
//
//     char buffer[4096];    // allocate 4096 bytes (4 KB) in a row on the stack
//                           // buffer is a pointer to the first byte
//                           // buffer == &buffer[0] == some address e.g. 0x7fff1234
//
//     buffer[0]             // byte at address 0x7fff1234
//     buffer[1]             // byte at address 0x7fff1235
//     buffer[4095]          // byte at address 0x7fff2233
//
// "Buffer" is just a human word for "a chunk of RAM I'm using to hold bytes
// temporarily while I move them from one place to another". The hardware has
// no concept of a buffer — it just sees addresses being read and written.
//
// WHERE IT LIVES: STACK VS HEAP
//
// The "stack" above is the same stack/heap you know from threads — the call stack.
// How you declare the buffer determines where it lives:
//
//     // --- STACK ---
//     //
//     // The stack is a small, fixed region of RAM your OS reserves for a thread
//     // when it starts — typically 8 MB on Linux, 1 MB on Windows. It has nothing
//     // to do with your total RAM (8 GB or otherwise). Think of it as a dedicated
//     // scratch-pad carved out of your RAM, not the whole thing:
//     //
//     //   your 8 GB of RAM, simplified:
//     //
//     //   address 0x0000 ──────────────────────────────────── address 0xFFFFFFFF
//     //   │  OS kernel  │  your program code  │  heap  │ ... │  stack (8 MB)  │
//     //
//     // The stack lives near the TOP of your program's address space (high addresses).
//     // The heap lives near the bottom and grows upward. They grow toward each other.
//     //
//     //
//     // WHAT IS RSP?
//     //
//     // RSP (Register Stack Pointer) is a special register inside the CPU itself —
//     // not a place in RAM, but a slot in the processor that holds one number:
//     // the memory address of the current top of the stack.
//     //
//     // The CPU has ~16 general purpose registers (RSP, RBP, RAX, RBX, ...).
//     // They are tiny storage slots built into the chip, each holding 8 bytes.
//     // RSP's only job is to track where the stack currently ends.
//     //
//     //
//     // WHAT DOES "ADJUST" MEAN?
//     //
//     // The stack grows DOWNWARD — toward lower addresses. So "allocating" space
//     // on the stack just means subtracting from RSP. The compiler emits one
//     // instruction at the top of your function:
//     //
//     //     sub rsp, 4096       ; RSP = RSP - 4096
//     //
//     // That's it. No OS call, no zeroing, no searching for free space.
//     // RSP now points 4096 bytes lower, and that gap IS your buffer.
//     //
//     // Concrete example — say RSP starts at 0x7FFF_F000 when your function begins:
//     //
//     //   before:  RSP = 0x7FFF_F000
//     //
//     //            sub rsp, 4096   →   RSP = 0x7FFF_F000 - 0x1000
//     //
//     //   after:   RSP = 0x7FFF_E000
//     //
//     //   the region 0x7FFF_E000 → 0x7FFF_F000 is now your buffer[4096]
//     //   buffer[0]    lives at 0x7FFF_E000
//     //   buffer[4095] lives at 0x7FFF_EFFF
//     //
//     // When the function returns, one instruction undoes it:
//     //
//     //     add rsp, 4096       ; RSP = RSP + 4096  →  back to 0x7FFF_F000
//     //
//     // The bytes in RAM didn't go anywhere — they still physically exist —
//     // but RSP moved back up past them, so the stack "forgets" that region.
//     // The next function call will overwrite those bytes without asking.
//     // That is why returning a pointer to a stack buffer is a disaster.
//     //
//     char buffer[4096];
//
//     // --- HEAP ---
//     //
//     // malloc() asks the OS for memory at runtime. The OS finds a free region
//     // somewhere in the heap, marks it as yours, and hands you a pointer to it.
//     // That memory is completely independent of the call stack — it stays alive
//     // until you explicitly release it with free(), regardless of which function
//     // called malloc() or whether that function has already returned.
//     //
//     char *buffer = malloc(4096);
//     free(buffer);   // you own it, you clean it up
//
//
//     // --- CONCRETE EXAMPLE: what goes wrong if you mix them up ---
//     //
//     // BAD — returning a pointer to a stack buffer:
//     //
//     //   char *get_buffer() {
//     //       char buf[4096];      // RSP moves down 4096 when we enter
//     //       return buf;          // we return the address — then RSP moves back up
//     //   }                        // that region is now "free" — next call stomps it
//     //
//     //   char *b = get_buffer();  // b points at memory the stack already reclaimed
//     //   b[0] = 'x';             //  Undefined Behavior— likely silent corruption or crash
//     //
//     // GOOD — heap buffer survives the function that created it:
//     //
//     //   char *get_buffer() {
//     //       char *buf = malloc(4096);   // lives on the heap, RSP not involved
//     //       return buf;                 // pointer is valid after return
//     //   }
//     //
//     //   char *b = get_buffer();   // b still points to valid memory
//     //   b[0] = 'x';              // fine
//     //   free(b);                 // caller's responsibility to clean up
//
// Stack buffers are faster and require no cleanup, but two things limit them:
//
//   1. SIZE — each thread gets a small stack (typically 1–8 MB total), so large
//             buffers should go on the heap
//   2. LIFETIME — a stack buffer dies when its function returns, so never return
//                 a pointer to one; the memory it points to is immediately reclaimed
//
// The stack in "call stack" and the stack data structure are the same idea:
// function calls push a frame on, returns pop it off — LIFO.
//
// ─────────────────────────────────────────────────────────────────────────────
//
// THE ABSTRACTION LAYERS — same physical RAM, different views
//
// Physical RAM (hardware):
//     one flat array of bytes
//     every byte has a real physical address
//     CPU accesses it directly via the memory bus
//     no concept of processes, users, or permissions
//     just: address in → byte out
//
// Kernel space (kernel's view):
//     kernel has full access to all physical RAM
//     kernel manages virtual memory — maps virtual addresses to physical ones
//     kernel has its own buffers:
//         TCP receive buffer   ← bytes that arrived from the network
//         TCP send buffer      ← bytes waiting to be sent
//         page cache           ← file contents(also bytes) cached in RAM
//     these are just regions of physical RAM the kernel tracks internally
//     the kernel writes to them directly using physical addresses
//
// Userspace (your process's view):
//     your process CANNOT access physical addresses directly
//     the CPU's MMU (Memory Management Unit) intercepts every memory access
//     and translates virtual address → physical address via the page table
//
//     your process thinks it owns address 0x7fff1234
//     the MMU translates that to physical address 0x2a4f8800 behind the scenes
//     two processes can both use address 0x7fff1234
//     they map to different physical locations — complete isolation
//
//     your buffer (char buffer[4096]) is:
//         from your process's view:  bytes at virtual address 0x7fff1234
//         from the kernel's view:    bytes at physical address 0x2a4f8800
//         from the hardware's view:  transistors on the RAM chip at row/col 0x2a4f8800
//
// ─────────────────────────────────────────────────────────────────────────────
//
// WHAT HAPPENS DURING read(fd, buffer, 4096)
//
//     read(fd=8, buffer, 4096)
//
//     your process:
//         buffer is at virtual address 0x7fff1234
//         syscall: "kernel, copy bytes from fd=8 into 0x7fff1234, up to 4096"
//         process blocks — parks the goroutine/thread, yields the CPU
//
//     kernel:
//         looks up fd=8 in your process's fd table → finds the TCP socket
//         checks TCP receive buffer — are bytes waiting?
//             no  → park the process, come back when NIC interrupt fires
//             yes → translate your virtual address 0x7fff1234 → physical 0x2a4f8800
//                   copy bytes from kernel TCP buffer → physical address 0x2a4f8800
//                   this is a direct memory write by the kernel
//                   returns number of bytes copied
//
//     your process resumes:
//         buffer[0..n] now contains the bytes the kernel wrote
//         from your perspective: data appeared in your buffer
//         what actually happened: kernel wrote to a physical RAM address
//         that your virtual address maps to
//
// The buffer you declared in C is not an abstraction of anything —
// it IS physical RAM, just accessed through the virtual address translation
// layer the MMU provides. The bytes the kernel copies into it are real
// electrons stored in real transistors on a real chip.
//
// Every layer above C (Go slice, Python bytes object, Java ByteBuffer)
// is a wrapper around this same mechanism. Somewhere underneath there is
// always a raw memory address the kernel writes bytes into.
// That address is always, ultimately, a location on a physical RAM chip.
// ─────────────────────────────────────────────────────────────────────────────

---

### 1. Everything is a File Descriptor

You already know everything is a file in Linux. A file descriptor (fd)
is just an integer the kernel gives back when you open anything:
open("/var/log/syslog")  → fd=3   ← a file on disk
socket()                 → fd=4   ← a network socket
accept()                 → fd=5   ← an incoming connection
pipe()                   → fd=6   ← a pipe between processes

From that point you use the exact same syscalls on all of them:
read(fd, buffer)    ← get bytes from whatever fd points to
write(fd, buffer)   ← send bytes to whatever fd points to
close(fd)           ← done with it

The kernel hides what's underneath. Your process doesn't know or care
if fd=5 is a file, a socket, or a pipe. It just reads and writes bytes.

The key thing to understand first is what existed before file descriptors, because that's what makes the design genius obvious.

Before Unix — the old world
Imagine you're writing a program in the 1960s that needs to read data from three different places:
reading from a file on disk:
    FILE *f = fopen("data.txt", "r");
    fread(buffer, size, count, f);
    fclose(f);

reading from a tape drive (hardware device):
    tape_open("/dev/tape0");
    tape_read(buffer, size);
    tape_close();

reading from another program through a pipe:
    pipe_create(&p);
    pipe_read(&p, buffer, size);
    pipe_destroy(&p);

Three completely different APIs. Three different sets of functions to learn. If you wanted to write a program that could read from any of those sources, you had to write three separate code paths and decide at compile time which one to use.
Worse — you couldn't compose programs. You couldn't take the output of program A and pipe it into program B without explicitly writing code to do that. Every combination required new glue code.

The Unix insight — everything is bytes
Ken Thompson looked at all these resources and noticed one thing: they all fundamentally produce or consume bytes. A file is bytes. A tape drive produces bytes. A pipe carries bytes. A network socket sends and receives bytes.
So why not give them all the same interface?
The kernel maintains one thing per open resource — a file descriptor, which is just an integer that indexes into a table:
fd table for your process:
    fd=0 → points to: keyboard
    fd=1 → points to: terminal screen
    fd=2 → points to: terminal screen
    fd=3 → points to: data.txt on disk
    fd=4 → points to: /dev/tape0 hardware device
    fd=5 → points to: one end of a pipe
    fd=6 → points to: TCP socket to 1.2.3.4:80
And now your entire program becomes:
c// read 100 bytes from whatever fd=3 points to
read(3, buffer, 100);

// write those bytes to whatever fd=1 points to
write(1, buffer, 100);
The same two lines work regardless of whether fd=3 is a file, a tape drive, a pipe, or a network socket. Your program doesn't know and doesn't care. The kernel translates the read() call into whatever the underlying hardware requires.

A concrete example — the pipe
You type this in your terminal:
bash cat /var/log/auth.log | grep "Failed" | wc -l
Three programs. None of them know about each other. Here is exactly what the shell does:
Step 1 — shell creates two pipes:
pipe 1:  [read_end_fd=3, write_end_fd=4]   ← between cat and grep
pipe 2:  [read_end_fd=5, write_end_fd=6]   ← between grep and wc
A pipe is just a kernel buffer with two ends. Write to one end, read from the other. That's it.
Step 2 — shell forks three child processes. Before executing each one, it manipulates their fd tables:
cat's fd table after shell manipulation:
    fd=0 → keyboard (unchanged)
    fd=1 → write end of pipe 1 (fd=4)   ← stdout now goes into pipe
    fd=2 → terminal (unchanged)

grep's fd table after shell manipulation:
    fd=0 → read end of pipe 1 (fd=3)    ← stdin now comes from pipe
    fd=1 → write end of pipe 2 (fd=6)   ← stdout goes into second pipe
    fd=2 → terminal (unchanged)

wc's fd table after shell manipulation:
    fd=0 → read end of pipe 2 (fd=5)    ← stdin comes from second pipe
    fd=1 → terminal (unchanged)          ← stdout goes to your screen
    fd=2 → terminal (unchanged)
Step 3 — shell execs each program. Now the magic:
cat thinks:
    "I will read /var/log/auth.log and write to stdout (fd=1)"
    cat writes 50,000 lines to fd=1
    cat has no idea fd=1 is a pipe, not a terminal

grep thinks:
    "I will read from stdin (fd=0) and write matches to stdout (fd=1)"
    grep reads lines from fd=0
    grep has no idea fd=0 is a pipe coming from cat
    grep writes matching lines to fd=1
    grep has no idea fd=1 is a pipe going to wc

wc thinks:
    "I will count lines from stdin (fd=0) and print the number"
    wc reads from fd=0
    wc has no idea it's reading grep's output
    wc prints "37280" to fd=1 which goes to your terminal
None of these programs were written to work with each other.
cat was written in 1971. grep was written in 1973. wc was written separately. They compose perfectly because they all speak the same language — read from fd=0, write to fd=1, that's it.
This is the entire unix philosophy. Write programs that read stdin and write stdout. The shell wires them together however you want by manipulating fds before exec. The programs never know.

## How kubectl, nginx, and sshd are all the same program

Every proxy on the internet — kubectl port-forward, nginx, sshd, HAProxy,
Cloudflare — is doing one thing: reading bytes from one fd and writing them
to another. The resources behind those fds change, but the loop never does.

---

### The universal proxy loop

```c
// this is the entire internet in 6 lines (The below example is a while true)
while (1) {
    n = read(fd_in,  buf, sizeof(buf));   // block until bytes arrive
    write(fd_out, buf, n);                // forward those bytes
}
```

Two goroutines run this loop simultaneously — one in each direction.
That's a complete bidirectional proxy. nginx is 200,000 lines of C.
The core of what it does is these 6 lines applied to millions of fd pairs.

---

### kubectl port-forward
situation:
your browser wants to talk to Grafana
Grafana is inside a pod with no public IP
kubectl is the middleman
kubectl has two fds open:
fd=8  ← TCP socket: browser connected to 127.0.0.1:3000
          bytes arriving here are HTTP requests from your browser
          "GET /grafana/dashboards HTTP/1.1"
          "Host: localhost:3000"
          "Cookie: grafana_session=abc123"

fd=9  ← TCP socket: kubectl connected to Kubernetes API server
          bytes going here travel through:
              HTTPS to API server
              API server → kubelet
              kubelet → veth pair → pod network namespace
              Grafana's accept() on port 3000
kubectl's loop:
goroutine 1 (browser → Grafana):
    n = read(fd=8, buf)        // browser sent "GET /grafana..."
                               // kernel copies those bytes into buf
                               // buf is a stack buffer, short lived,
                               // just a temporary holding area
    write(fd=9, buf[:n])       // forward exact same bytes to API server
                               // kubectl never parsed them
                               // never looked at the HTTP headers
                               // never knew it was HTTP at all
                               // just bytes in, bytes out

goroutine 2 (Grafana → browser):
    n = read(fd=9, buf)        // Grafana sent back dashboard JSON
                               // arrived through API server → kubectl
    write(fd=8, buf[:n])       // forward to browser
                               // again, kubectl has no idea
                               // it's JSON, or HTML, or an image
                               // just bytes
kubectl is grep.
fd=8 is its stdin  — bytes come in from the browser.
fd=9 is its stdout — bytes go out to the API server.
The bytes are HTTP. kubectl doesn't know. Doesn't matter.

---

### nginx
situation:
browser connects to your server on port 443
nginx is the middleman between the browser and FastAPI
nginx has two fds open per request:
fd=12 ← TCP socket: browser connected to nginx port 443
           bytes arriving here are HTTPS requests
           nginx DOES decrypt TLS here — it has to
           because it needs to read the HTTP path to decide
           which upstream to route to (/api/ → FastAPI, /grafana/ → Grafana)
           this is the ONE thing that makes nginx smarter than kubectl
           it understands enough of the protocol to route

fd=13 ← TCP socket: nginx connected to FastAPI on port 8000
           plain HTTP inside the cluster, no TLS needed
           nginx re-encodes the request and forwards it
nginx's loop after routing decision:
goroutine 1 (browser → FastAPI):
    n = read(fd=12, buf)       // read decrypted HTTP request body
                               // nginx already read the headers to route
                               // now it's just forwarding the body bytes
    write(fd=13, buf[:n])      // forward to FastAPI

goroutine 2 (FastAPI → browser):
    n = read(fd=13, buf)       // FastAPI's JSON response
    write(fd=12, buf[:n])      // forward to browser, TLS encrypts on the way out
nginx is slightly smarter than kubectl —
it reads the HTTP headers to make a routing decision,
then becomes a dumb byte forwarder for the body.
The routing logic is the 200,000 lines of C.
The actual data movement is still just read() → write().

---

### sshd
situation:
your laptop's SSH client connected to the droplet on port 22
you used -L 3000:localhost:3000
sshd is the middleman between your laptop and kubectl
sshd has two fds open:
fd=5  ← TCP socket: your laptop's SSH client connected on port 22
          bytes arriving here are ENCRYPTED SSH packets
          sshd decrypts them
          inside the decrypted bytes is a direct-tcpip channel request:
          "connect to localhost:3000 on your end and splice the streams"

fd=6  ← TCP socket: sshd connected to 127.0.0.1:3000 on the droplet
          this is kubectl port-forward's listening socket
          kubectl's accept() just returned fd=8 for this connection
sshd's loop:
goroutine 1 (your laptop → kubectl):
    n = read(fd=5, buf)        // encrypted SSH packet from laptop
    decrypt(buf, n)            // sshd understands SSH protocol enough
                               // to unwrap the encryption
                               // extracts the raw bytes your browser sent
    write(fd=6, buf[:n])       // forward raw bytes to kubectl
                               // kubectl has no idea sshd decrypted anything
                               // kubectl just sees bytes arriving on fd=8

goroutine 2 (kubectl → your laptop):
    n = read(fd=6, buf)        // Grafana's response bytes from kubectl
    encrypt(buf, n)            // wrap in SSH packet
    write(fd=5, buf[:n])       // send encrypted back to your laptop
                               // SSH client on laptop decrypts
                               // browser receives the raw response
sshd is smarter than kubectl in one way —
it handles SSH encryption and channel multiplexing.
but the data movement is still read() → write().

---

### The full chain together
browser
write(fd=browser_socket, "GET /grafana/...")   // browser sends request
laptop SSH client
read(fd=browser)                               // reads browser's bytes
encrypt(bytes)                                 // wraps in SSH
write(fd=ssh_connection)                       // sends to droplet
droplet sshd
read(fd=ssh_connection)                        // receives encrypted packet
decrypt(bytes)                                 // unwraps SSH
write(fd=kubectl_socket)                       // forwards to kubectl
kubectl port-forward
read(fd=kubectl_socket)                        // receives raw HTTP bytes
write(fd=api_server_connection)               // forwards to API server
kubernetes api server
read(fd=kubectl_connection)                    // receives bytes
write(fd=kubelet_connection)                   // forwards to kubelet
kubelet
read(fd=api_server)                            // receives bytes
write(fd=veth_pair)                            // crosses namespace boundary
grafana pod
read(fd=eth0_socket)                           // bytes arrive
// Grafana actually parses them — it's the destination, not a proxy
// this is the first process in the chain that cares what the bytes mean

Every hop except Grafana is doing read() → write().
Every hop except Grafana has no idea what the bytes mean.
Grafana is the first process that opens the envelope and reads the letter.

The file descriptor abstraction from 1971 made all of this possible —
one interface for everything that is a stream of bytes,
composable by wiring fds together,
scaling from a pipe between two shell commands
to a chain of proxies spanning a laptop, a droplet, and a Kubernetes pod.

**The kernel's file descriptor table:**

Every process has its own fd table — a simple array the kernel maintains:
process fd table (per process):
index → pointer to kernel file object
fd=0  → kernel file object → /dev/tty   (your terminal)
fd=1  → kernel file object → /dev/tty   (same terminal)
fd=2  → kernel file object → /dev/tty   (same terminal)
fd=3  → kernel file object → /var/log/syslog
fd=4  → kernel file object → socket (TCP connection to 1.2.3.4:80)
fd=5  → kernel file object → socket (another connection)

The fd number (3, 4, 5) is just an index into this array.
The kernel file object behind it is where the real state lives —
file position, socket buffers, connection state, etc.

When you fork(), the child gets a copy of the fd table —
same indices, same kernel objects. That's how parent and child
share file descriptors across fork/exec.

**The routing table — how the kernel decides where packets go:**

When your process does `connect(fd, 8.8.8.8:53)` the kernel
doesn't just send the packet blindly — it consults the routing table
to decide which interface to use:
ip route show
default via 10.0.0.1 dev eth0          ← anything not matched below: use eth0, gateway 10.0.0.1
10.0.0.0/8 dev eth0 proto kernel       ← traffic to 10.x.x.x: use eth0 directly (same network)
127.0.0.0/8 dev lo proto kernel        ← traffic to 127.x.x.x: use loopback, never leave machine
10.42.0.0/16 dev flannel.1             ← traffic to pod network: use flannel tunnel interface

The kernel reads these top to bottom, most specific match wins:
connect to 8.8.8.8
→ check: is 8.8.8.8 in 127.0.0.0/8?  no
→ check: is 8.8.8.8 in 10.0.0.0/8?   no
→ check: is 8.8.8.8 in 10.42.0.0/16? no
→ default: use eth0, send to gateway 10.0.0.1
connect to 127.0.0.1
→ check: is 127.0.0.1 in 127.0.0.0/8? yes
→ use lo interface
→ packet never leaves the machine
→ kernel loops it back internally
connect to 10.42.0.17 (a pod IP)
→ check: is 10.42.0.17 in 10.42.0.0/16? yes
→ use flannel.1 interface
→ flannel encapsulates packet and sends to the node that owns that pod

This is why kubectl port-forward binding to 127.0.0.1 is unreachable
from outside — traffic to 127.x.x.x hits the lo route,
never reaches eth0, never leaves the machine.
Not a firewall rule. Just routing.

**The full picture — fd + routing + syscalls together:**
your process
write(fd=4, "GET / HTTP/1.1")    ← write to socket fd
│
▼
kernel TCP layer
│  buffers the bytes
│  wraps in TCP segment (source port, dest port, seq number)
│  wraps in IP packet   (source IP, dest IP)
│  consults routing table → which interface?
│
▼
network interface (eth0 or lo)
│
├── lo:   kernel loops packet back, delivers to listening process
│         no hardware involved
│
└── eth0: kernel hands to NIC driver
NIC driver sends electrical signal on the wire
packet travels to destination

Every layer is invisible to your process.
You called write(). The kernel handled everything else.
That's the unix contract — simple interface, complex implementation hidden underneath.

---

### 2. What a Socket Actually Is

A socket is a kernel object representing one end of a network connection.
When you call `socket()` the kernel creates it and returns an fd.
At this point it's just an empty endpoint — no address, no connection, nothing.
socket()
→ kernel creates socket object in memory
→ returns fd=7
→ fd=7 exists but is not bound to any address yet
→ nothing can reach it

Think of it as a telephone that exists but has no phone number assigned yet.

---

### 3. The Server Lifecycle — socket, bind, listen, accept

A server goes through four steps:

**socket()** — create the endpoint:
fd=7 = socket()
telephone exists, no number yet

**bind()** — assign an address and port:
bind(fd=7, 127.0.0.1:3000)
telephone now has number 3000
only reachable on 127.0.0.1 (loopback)

**listen()** — declare "I am a server, start accepting connections":
listen(fd=7, backlog=128)
telephone is now ringing-enabled
kernel creates two internal queues:
SYN queue    ← connections mid-handshake
               (SYN received, SYN-ACK sent, waiting for final ACK)

accept queue ← fully established connections
               waiting for your process to claim them
backlog=128 means accept queue holds max 128 connections
if you don't drain it fast enough kernel drops new ones silently

**accept()** — claim an incoming connection:
fd=8 = accept(fd=7)
fd=7 keeps listening forever  ← the "phone number", always open
fd=8 is the live conversation ← this specific call
your process blocks on accept() until someone connects
when they do, kernel returns fd=8
now you have two fds:
fd=7 → still listening for more connections
fd=8 → the live connection to this specific client

---

### 4. The Client Lifecycle — socket, connect

A client only needs socket() and connect():
fd=9 = socket()                ← create endpoint
connect(fd=9, 1.2.3.4:80)     ← establish connection to server
kernel performs the TCP 3-way handshake:
client → SYN        → server
client ← SYN-ACK    ← server
client → ACK        → server
after ACK, connect() returns
fd=9 is now a live connection to the server

---

### 5. TCP is a Byte Stream, Not Messages

This is the most misunderstood thing about networking.

TCP does not have messages. It has a continuous stream of bytes —
like water through a pipe. You cannot tell where one "message" ends
and the next begins just from TCP alone.
sender does:
write(fd, "hello world")   ← writes 11 bytes
receiver might see:
read(fd, buf)  → "hello"       ← 5 bytes arrived first
read(fd, buf)  → " wor"        ← 4 bytes
read(fd, buf)  → "ld"          ← 2 bytes

TCP can split or batch bytes however it wants for efficiency.
This is why every protocol built on TCP includes a length field or delimiter:
HTTP:           Content-Length: 1234   ← read exactly 1234 bytes
HTTP chunked:   chunk size header      ← read N bytes, then next chunk
SPDY:           frame header + length  ← read header, then that many bytes
SSH:            packet length field    ← same pattern

Without this, you would never know if you got a complete response or half of one.

---

### 6. IP Addresses and Ports

An IP address identifies a machine. A port identifies a process on that machine.
1.2.3.4:80
│       │
│       └── port 80 → nginx owns this port
└────────── 1.2.3.4 → this specific machine

Special addresses:
127.0.0.1   → loopback — the machine talking to itself
traffic never leaves the machine
never hits the NIC, never hits the network
kernel handles it entirely in memory
0.0.0.0     → all interfaces — listen on every network interface
your machine has:
lo      127.0.0.1   (loopback)
eth0    10.0.1.5    (real network)
binding to 0.0.0.0:3000 accepts connections on both
127.0.0.1:3000 AND 10.0.1.5:3000 simultaneously

This is why kubectl port-forward binds to 127.0.0.1 not 0.0.0.0 —
it is intentionally only reachable from the same machine.

---

### 7. Network Interfaces — the Doors to the Network

Your machine has network interfaces — each one is a door to a different network:
lo      → loopback interface
127.0.0.0/8 range
packets to 127.x.x.x never leave the machine
kernel loops them back internally, no NIC involved
eth0    → real network interface
connected to the actual NIC hardware
packets go: eth0 → NIC driver → physical cable → internet

When you send a packet the kernel checks its routing table:
destination 127.0.0.1  → use lo  (never leaves machine)
destination 8.8.8.8    → use eth0, via gateway 10.0.0.1
ip route show          ← see the routing table yourself

---

### 8. Full TCP Connection Journey

What actually happens when your browser connects to a server:
your laptop
browser: connect(fd, 1.2.3.4:443)
kernel builds TCP SYN packet:
source IP:   192.168.1.5   (your laptop's IP)
source port: 54321         (random ephemeral, kernel picks it)
dest IP:     1.2.3.4
dest port:   443
kernel checks routing table → use eth0
kernel hands packet to NIC driver
NIC sends packet onto the wire
internet
packet hops through routers
each router reads dest IP, forwards toward 1.2.3.4
server
NIC receives packet
kernel reads dest port: 443 → finds nginx owns it
nginx's accept() unblocks, returns new fd
nginx sends SYN-ACK
your laptop
receives SYN-ACK → sends ACK
connect() returns — connection established
both sides now have a live fd they can read/write

---

### 9. The Splice Proxy Pattern — the Core of Everything

Once you have two file descriptors open, proxying between them is trivial:
fd=8  ← connection from browser
fd=9  ← connection to backend
goroutine 1 (browser → backend):
while true:
n = read(fd=8, buf)    ← block until browser sends bytes
write(fd=9, buf[:n])   ← forward those bytes to backend
goroutine 2 (backend → browser):
while true:
n = read(fd=9, buf)    ← block until backend sends bytes
write(fd=8, buf[:n])   ← forward those bytes to browser

That is a complete proxy in 6 lines. nginx, kubectl port-forward, sshd —
they all do this exact loop. The process has no idea what the bytes mean.
It just moves them from one fd to another.

This is called splice proxying. The proxy is dumb by design —
it does not parse HTTP, does not understand Grafana responses.
It just copies bytes. This is why "userspace proxying" means
nothing special — just processes doing read() → write() loops.

---

### 10. What SSH Actually Is

SSH is a protocol running over one TCP connection that provides:
encryption      ← all bytes encrypted, nobody can read them in transit
authentication  ← prove identity via private key
multiplexing    ← multiple independent channels inside one TCP connection

The multiplexing part is key. Inside one TCP connection on port 22:
channel 1  ← your shell session
channel 2  ← a port forward tunnel (-L)
channel 3  ← another port forward tunnel
channel 4  ← SFTP file transfer

All simultaneously over one TCP connection.
SSH has its own framing (like HTTP Content-Length) so both sides
know which channel each packet belongs to.

---

### 11. SSH Local Port Forwarding — the -L Flag

```bash
ssh -L 3000:localhost:3000 deploy@1.2.3.4
```

Syntax: `-L <local-port>:<remote-host>:<remote-port>`

"Listen on my laptop's port 3000. For every connection that arrives,
ask the SSH server on the droplet to connect to its own localhost:3000,
then splice the two streams together."
on your laptop:
SSH client: socket() + bind(127.0.0.1:3000) + listen()
SSH client: connect() to 1.2.3.4:22
when browser connects to laptop localhost:3000:
SSH client: accept() → fd=browser
SSH client sends through encrypted session:
"open a direct-tcpip channel, connect to localhost:3000 on your end"
on the droplet:
sshd receives the channel-open request
sshd: connect(fd=remote, 127.0.0.1:3000)
both sides do the splice loop:
laptop SSH:   read(browser_fd) → encrypt → write(ssh_fd)
droplet sshd: read(ssh_fd) → decrypt → write(kubectl_fd)

Result — a pipe across machines:
browser ←→ SSH tunnel (encrypted) ←→ sshd ←→ kubectl port-forward

---

### 12. Network Namespaces — How Pods Get Isolation

A network namespace gives each pod its own isolated network stack:
its own loopback      127.0.0.1 means something different inside each pod
its own eth0          10.42.0.17 or whatever the pod IP is
its own routing table
its own port space    two pods can both bind port 3000, no conflict
its own firewall rules

Host machine and each pod live in separate namespaces:
host namespace:
lo      127.0.0.1
eth0    1.2.3.4         ← the droplet's real public IP
grafana pod namespace:
lo      127.0.0.1       ← completely separate loopback
eth0    10.42.0.17      ← virtual interface, private cluster IP only

Processes inside the pod see their namespace only.
They think they are on their own machine.

---

### 13. veth Pairs — How Pods Connect to the Host

A veth pair is two virtual interfaces connected like a pipe.
Bytes written to one come out the other:
host namespace              pod namespace
veth0    ←──────────→    eth0
(host end)               (pod end, what the pod calls its network card)
kubelet writes to veth0  → bytes appear at pod's eth0
pod writes to its eth0   → bytes appear at host's veth0

This is how traffic crosses namespace boundaries.
The kubelet connects to a pod by writing to its end of the veth pair.

---

## 🔌 Accessing Grafana: Network Deep-Dive

The access workflow chains **two separate tunnels**. Understanding both is useful for debugging and for interviews.

```bash
# On the droplet:
kubectl port-forward -n portfolio svc/grafana 3000:3000

# On your laptop:
ssh -L 3000:localhost:3000 deploy@<droplet-ip>

# Then open: http://localhost:3000
```

---

### The Big Picture
Your Browser (laptop:3000)
│
│  SSH tunnel  [-L 3000:localhost:3000]
│
Droplet localhost:3000
│
│  kubectl port-forward
│
Kubernetes API Server
│  (SPDY/WebSocket upgrade over HTTPS)
│
kubelet on the node
│
│  connect() into pod network namespace
│
Grafana Pod — port 3000

Your laptop never has a direct route to the pod. The pod lives inside a private cluster overlay network (e.g. flannel, Calico). Both tunnels together bridge that gap without opening any firewall ports or binding anything publicly.

---

### Tunnel 1 — `kubectl port-forward`

```bash
kubectl port-forward -n portfolio svc/grafana 3000:3000
```

`kubectl` runs as a **userspace process** on the droplet. It:

1. Creates a TCP **server socket**, binds it to `127.0.0.1:3000` (loopback only — not reachable from outside the droplet), and calls `listen()`.
2. When a connection arrives and `accept()` returns a new file descriptor, `kubectl` opens an **HTTPS connection to the Kubernetes API server** using credentials from `~/.kube/config`.
3. It sends an HTTP request with an `Upgrade: SPDY/3.1` header (newer versions use WebSocket). The API server accepts the upgrade, turning the connection from request/response into a **persistent bidirectional byte stream**.
4. Over that stream, `kubectl` opens a **port-forward channel** — a logical sub-stream inside the SPDY/WebSocket session.
5. The API server forwards the channel to the **kubelet** running on the node.
6. The kubelet calls `connect()` into the **pod's network namespace** (crossing through the veth pair that the CNI plugin set up), reaching Grafana's process on port 3000.

From this point, bytes written into the droplet's `127.0.0.1:3000` socket travel through all those hops and arrive at the Grafana process — and vice versa. Every hop is **userspace proxying**: no TUN/TAP devices, no kernel tunneling, just processes copying bytes between file descriptors.

**Why loopback only?**
The default bind address is `127.0.0.1`, not `0.0.0.0`. Nothing on the network can reach it. You *can* override with `--address=0.0.0.0`, but that exposes the port with no authentication. The SSH tunnel is the right way to bring it to your laptop.

#### The low-level socket lifecycle

This is what actually happens inside the kernel when `kubectl port-forward` starts:

socket()   → kernel creates a socket object, returns fd=7
(just an empty endpoint, not bound to anything yet)
bind()     → attaches fd=7 to 127.0.0.1:3000
(reserves the address/port combination in the kernel)
listen()   → marks fd=7 as passive — "I am a server, I will wait"
kernel now maintains two internal queues for this socket:
- SYN queue:     TCP handshakes in progress (SYN received, SYN-ACK sent)
- accept queue:  fully established connections waiting to be claimed
accept()   → kubectl blocks here, sleeping, until a client connects
when a connection completes the 3-way handshake the kernel
moves it from the SYN queue → accept queue
accept() dequeues it and returns a NEW fd=8
fd=7 keeps listening — fd=8 is the live connection
read(fd=8) → kubectl reads bytes the client sent
if no bytes yet, the call blocks until data arrives
returns however many bytes are currently in the kernel receive buffer
(not necessarily all of them — you must loop)
write(fd=9)→ kubectl writes those same bytes into fd=9
fd=9 is the outbound HTTPS connection to the API server
kernel puts them in the send buffer and ACKs when the other
side receives them — write() does not mean "delivered"


The critical detail: `kubectl` is doing nothing clever. It is literally:
while true:
n, err = read(fd=8, buf)     # block until browser sends something
write(fd=9, buf[:n])         # forward it to the API server

and the same loop in the other direction on a second goroutine. This is called **splice proxying** — the process is a dumb byte pipe. It has no idea the bytes are HTTP, or Grafana metrics, or anything else. It just moves them.

**What `listen()` backlog actually means:**
`listen(fd, backlog=128)` — the `128` is the max size of the accept queue. If connections arrive faster than `accept()` is called to drain them, the kernel silently drops the excess. For port-forward this never matters (one connection at a time), but it's why high-traffic servers call `accept()` in a tight loop or across multiple threads.

**What `read()` actually returns:**
`read()` returns whatever bytes are sitting in the kernel's TCP receive buffer at that moment — which is not guaranteed to be a complete message. TCP is a **byte stream**, not a message protocol. A single `write("hello")` on one end might arrive as `"hel"` and `"lo"` on two separate `read()` calls. Protocols like HTTP and SPDY solve this by including a `Content-Length` or frame header so the reader knows when a full message has arrived. `kubectl` doesn't need to care about this because it is forwarding raw bytes — the SPDY framing is handled by the Go library underneath, not by kubectl's proxy loop directly.

#### Dummies example

Think of it like a **mail room inside a locked building**.

Grafana is an office on floor 10 — no one from outside can walk in directly. `kubectl port-forward` is a mail room clerk who sits at a desk in the lobby (`127.0.0.1:3000`). The clerk only accepts mail from inside the building (loopback — no external access).

The low-level part is the clerk's actual routine:
- `socket()` — the clerk is hired but has no desk yet
- `bind()` — they are assigned desk `127.0.0.1:3000`
- `listen()` — they sit down and start waiting for mail to arrive
- `accept()` — a letter arrives; the clerk picks it up (this is blocking — they just sit there until something comes)
- `read()` — they read however much of the letter has been slid under the door so far (might be half a page — they have to wait for the rest)
- `write()` — they copy every byte of it into a new envelope and pass it to the next person in the chain

Nobody in the chain reads the letter. They just pass envelopes. The building manager (API server), the floor supervisor (kubelet), and the clerk are all doing the exact same thing: `read` from one fd, `write` to another.

---

### Tunnel 2 — `ssh -L`

```bash
ssh -L 3000:localhost:3000 deploy@<droplet-ip>
```

The flag syntax is: `-L <local-port>:<destination-host>:<destination-port>`

This tells the SSH client: **"Listen on my laptop's port 3000. For every connection that arrives, ask the SSH server on the droplet to open a TCP connection to its own `localhost:3000`, and splice the two byte streams together."**

**On your laptop**, the SSH client:
1. Creates a TCP server socket bound to `127.0.0.1:3000` and calls `listen()`.
2. When your browser calls `connect()`, `accept()` returns a new connected socket (file descriptor).
3. SSH reads bytes from that fd, **encrypts them**, and writes them into the existing SSH TCP session to the droplet.

**On the droplet**, `sshd`:
1. Receives the encrypted bytes, decrypts them.
2. Sees a **`direct-tcpip` channel-open request** (this is SSH's internal channel type for local port forwarding).
3. Calls `connect()` to `127.0.0.1:3000` on the droplet — exactly where `kubectl port-forward` is listening.
4. Splices the streams: bytes from your laptop flow into that socket; bytes back get encrypted and sent to your laptop.

**The SSH multiplexing layer:**
SSH runs over a single TCP connection between your laptop and the droplet. Inside that TCP session, SSH uses its own binary packet protocol with independent **channels**, each with their own flow control and window sizing — separate from TCP's own. Local port forwarding is just one channel type. You could have multiple `-L` tunnels, a shell session, and SFTP all multiplexed over the same single TCP connection simultaneously.

---

### Full Packet Journey

When you open `http://localhost:3000` in your browser:

Browser: connect() → laptop 127.0.0.1:3000
SSH client: accept() the connection
SSH client: send channel-open (direct-tcpip) through encrypted TCP to droplet
sshd on droplet: receive and decrypt
sshd: connect() → droplet 127.0.0.1:3000
kubectl port-forward: accept() that connection
kubectl: send SPDY/WebSocket port-forward frame to Kubernetes API server (HTTPS)
API server: forward to kubelet
kubelet: connect() into pod network namespace → Grafana port 3000
Grafana: accept() — sees a normal inbound TCP connection

Response bytes travel back through all 9 hops in reverse,
each layer re-encrypting or re-framing as needed.

---

### Why This Architecture

| Problem | How it's solved |
|---|---|
| Grafana pod has no public IP | Pod lives in a private cluster CIDR; kubectl tunnels through the already-authenticated API server |
| Droplet's port-forward binds only to loopback | SSH `-L` forwards it securely to your laptop over the existing SSH connection |
| No new firewall rules needed | Everything rides port 22 (SSH); no new ingress required |
| No credentials exposed on the wire | SSH encrypts the tunnel end-to-end; kubectl uses mTLS to the API server |

---

### Key Concepts Summarised

- **`listen()` / `accept()` / `connect()`** — both tunnels create server sockets that block on `accept()`, then splice the resulting fd with an outbound `connect()` fd. This is the entire mechanism.
- **File descriptors** — `accept()` and `connect()` both return fds. The SSH and kubectl processes are doing fd-to-fd byte copying (splicing) in userspace.
- **SPDY/WebSocket upgrade** — converts a standard HTTP request/response into a raw stream without opening a new TCP connection. The API server reuses the upgraded connection.
- **SSH channels** — the `direct-tcpip` channel type is how SSH implements local port forwarding. Multiple port-forwards share one TCP session via channel multiplexing.
- **Network namespaces** — each pod gets its own network namespace with its own loopback and virtual ethernet interface. The kubelet's `connect()` crosses into it via the veth pair created by the CNI plugin.
- **Userspace proxying** — no kernel-level tunneling anywhere in this chain. Every hop is a process reading from one socket and writing to another.

---