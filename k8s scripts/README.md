# Portfolio K8s - DigitalOcean Droplet Deployment

A Kubernetes (k3s) deployment showcasing:
- **PostgreSQL Primary + Read Replica** — Demonstrates database replication
- **Image Service with NSFW Detection** — TensorFlow-based content moderation
- **Redpanda Event Streaming** — Kafka-compatible broker with explicit partition routing
- **Full stack on a $21/mo droplet** — 2GB RAM + swap, all features enabled

---

## Droplet Specs

- **Plan**: Premium AMD $21/mo
- **RAM**: 2 GB (+ 2 GB swap added by install script)
- **CPU**: 2 AMD CPUs
- **Disk**: 60 GB NVMe SSD
- **Transfer**: 3 TB
- **OS**: Ubuntu 24.04 (recommended, many DigitalOcean Marketplace 1-Click Apps are built on Ubuntu, and for a simple app like this, Ubuntu is widespread and low-friction. [Reference](https://docs.digitalocean.com/products/marketplace/droplet-1-click-apps/))

---

## User Setup

All scripts run as a **regular user with sudo privileges** — never as root directly.

```bash
# If you only have root, create a user first:
adduser deploy
usermod -aG sudo deploy
su - deploy
```

---

## What's Different from a Local 4GB+ Setup

| Setting | Local (4GB+) | Droplet (2GB) |
|---------|-------------|---------------|
| Backend replicas | 2 | **1** |
| Image service replicas | 2 | **1** |
| NSFW detection | Enabled | **Enabled** |
| Backend workers | 2 | **1** |
| PG shared_buffers | 256MB | **128MB** |
| PG replica shared_buffers | 256MB | **64MB** |
| Redis maxmemory | 256MB | **64MB** |
| DB pool size | 5-20 | **2-8** |
| Redpanda memory | 1GB | **512MB** |
| Swap | None | **2GB** |

---

## 🚀 Quick Start

### 1. Create Droplet & SSH In
```bash
ssh deploy@143.110.154.54
# or ssh root, then create a user (see User Setup above)
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
> ⚠️ This takes 10-20 min on 2 CPUs. The image-service (TensorFlow wheels) is the slowest.

### 4.5. Resend API Key
```bash
./set-resend-key.sh
# Enter your key
# Script will ask if you want to update Kubernetes secret
# Choose "yes" to update immediately
```

### 5. Deploy
```bash
./deploy-k3s-local.sh
```

### 6. Post-Deploy
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

# Pytest testing if needed
kubectl exec -n portfolio deployment/backend -- \
  pytest app/tests/ -v
```
### 7. Access
```
http://143.110.154.54/front-page/front-page/front-page.html
http://143.110.154.54/front-page/docs
http://143.110.154.54/front-page/health
```

---

## What Needs sudo vs What Doesn't

| Command | sudo needed? | Why |
|---------|-------------|-----|
| `kubectl ...` | **No** | kubeconfig copied to ~/.kube/config |
| `docker build` | **No** | user added to docker group |
| `sudo k3s ctr images import` | **Yes** | k3s containerd is root-owned |
| Swap/sysctl/apt | **Yes** | system-level operations |

The scripts handle this automatically — you just need a user with sudo access.

---

## 🎯 What This Demonstrates

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

### 2. Confirm replica is in recovery mode

**Note**: The replica uses the official `postgres:16` image (not the custom `portfolio-postgres:16`),
so it doesn't have `.pgpass` configured. You need to provide the password explicitly:
```bash
# Get the password from Kubernetes secret
POSTGRES_PASS=$(kubectl get secret portfolio-secrets -n portfolio -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)

# Check if replica is in recovery mode
kubectl exec -n portfolio postgres-replica-0 -- \
  bash -c "PGPASSWORD='${POSTGRES_PASS}' psql -U postgres -d postgres -c 'SELECT pg_is_in_recovery();'"
# Should return: t (true)
```

### 3. Image Service with NSFW Detection
- TensorFlow model loaded at startup (~500MB)
- Automatic content moderation on image uploads
- Runs within swap on 2GB, functional but not fast
```bash
# Check NSFW model status (verify model is loaded)
kubectl logs -n portfolio deployment/image-service | grep -i "nsfw\|model\|loaded"

# Check health endpoint (shows full NSFW config)
# First, check if port 8080 is in use and kill it if needed
sudo lsof -i :8080
# If port is in use, kill the process: sudo kill -9 <PID>

kubectl port-forward -n portfolio svc/image-service 8080:8080 &
sleep 2
curl http://localhost:8080/health
# Expected: {"status":"healthy",...,"nsfw":{"enabled":true,"model_loaded":true,...}}

# Watch image processing in real-time
kubectl logs -n portfolio deployment/image-service -f
```

### 4. Redpanda Event Streaming
- Kafka-compatible broker running as a StatefulSet with persistent storage
- Every login and logout publishes an event; auth never blocks on Kafka
- Partition routing is explicit: `es` users → partition 0, `en` users → partition 1
- Producer self-heals: if Redpanda was down at startup, next publish triggers lazy reconnect

```bash
# Verify Redpanda broker is healthy
kubectl exec -n portfolio redpanda-0 -- \
  rpk cluster health --api-urls=localhost:9644
# Expected: HEALTHY: true, Controller: redpanda-0

# List all topics and confirm both were created by the init Job
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic list --brokers=localhost:9092
# Expected:
#   NAME           PARTITIONS  REPLICAS
#   user-logins    2           1
#   user-logouts   2           1

# Inspect partition layout for user-logins
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic describe user-logins --brokers=localhost:9092
# Shows partition 0 and partition 1, both on broker 0

# Watch events arrive in real time (partition 0 = es users)
# Keep this running, then trigger a login in another terminal
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic consume user-logins --brokers=localhost:9092 --num=5
# Each login shows: {"user_uuid":"...","email":"...","lang":"es"} on partition 0
#                or {"user_uuid":"...","email":"...","lang":"en"} on partition 1

# Confirm message count per partition after a few logins
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic describe user-logins --print-watermarks --brokers=localhost:9092
# HIGH-WATERMARK column shows how many messages each partition has received

# Check that the producer connected from the backend side
kubectl logs -n portfolio deployment/backend | grep "kafka_producer_started"
# Expected: {"event":"kafka_producer_started","brokers":"redpanda:9092",...}

# Verify events are being published (after a login attempt)
kubectl logs -n portfolio deployment/backend | grep "kafka_event_published"
# Expected: {"event":"kafka_event_published","topic":"user-logins","key":"en","partition":1,...}

# Check for any producer failures (should be empty in normal operation)
kubectl logs -n portfolio deployment/backend | grep "kafka_event_failed\|kafka_event_skipped"

# Inspect the init Job logs (available for 5 minutes after completion)
kubectl logs -n portfolio -l job-name=redpanda-init
# Shows the rpk topic create commands and final topic list
```

## Memory Budget (NSFW Enabled)

```
Component             Request    Limit
─────────────────────────────────────
k3s system            ~300MB     -
PostgreSQL Primary    192MB      384MB
PostgreSQL Replica    128MB      256MB
Redis                 32MB       96MB
MinIO                 128MB      256MB
Image Service         384MB      768MB  (TensorFlow NSFW)
Backend               192MB      512MB
Nginx                 32MB       128MB
Redpanda              512MB      768MB
─────────────────────────────────────
Total Requests        ~1900MB
Total Limits          ~3168MB (will use swap)
Available             2048MB RAM + 2048MB swap
```

---

## 🔧 Common Commands

### View Running Services
```bash
# All pods
kubectl get pods -n portfolio -o wide

# Key demo components
kubectl get pods -n portfolio -l 'app in (postgres-primary,postgres-replica,image-service,redpanda)'
```

### Check Database Activity
```bash
# Connect to primary (writes)
kubectl exec -it -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio'

# Once inside psql, all app tables are in the proveo schema:
#   \dt proveo.*                        -- list all tables
#   SET search_path TO proveo;          -- avoid typing proveo. every time
#   SELECT * FROM proveo.users LIMIT 5;
#   SELECT * FROM proveo.companies LIMIT 5;

# Connect to replica (reads only)
# Note: Replica uses official postgres:16 image without .pgpass, so password must be provided explicitly
POSTGRES_PASS=$(kubectl get secret portfolio-secrets -n portfolio -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
kubectl exec -it -n portfolio -c postgres postgres-replica-0 -- \
  bash -c "PGPASSWORD='${POSTGRES_PASS}' psql -U postgres -d portfolio"

# Check replication lag
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT client_addr, state, replay_lag FROM pg_stat_replication;"'

# Quick table counts (primary)
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT schemaname, tablename, n_live_tup FROM pg_stat_user_tables WHERE schemaname = '"'"'proveo'"'"' ORDER BY n_live_tup DESC;"'

# List all tables in proveo schema
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c "\dt proveo.*"'
```

### Check Redpanda Activity
```bash
# Broker health
kubectl exec -n portfolio redpanda-0 -- \
  rpk cluster health --api-urls=localhost:9644

# Topic list
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic list --brokers=localhost:9092

# Consume recent events from both topics
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic consume user-logins --brokers=localhost:9092 --num=10

kubectl exec -n portfolio redpanda-0 -- \
  rpk topic consume user-logouts --brokers=localhost:9092 --num=10

# Message offsets per partition (shows total event count)
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic describe user-logins --print-watermarks --brokers=localhost:9092
```

### Monitor Logs
```bash
# Backend logs (includes kafka_event_published entries)
kubectl logs -n portfolio deployment/backend -f

# Image service logs
kubectl logs -n portfolio deployment/image-service -f

# Redpanda broker logs
kubectl logs -n portfolio redpanda-0 -f
```

### Access Services via Port-Forward (From inside the Droplet)
```bash
# API docs
kubectl port-forward -n portfolio svc/backend 8000:8000
# Visit curl http://localhost:8000/docs in another console

# MinIO console
kubectl port-forward -n portfolio svc/minio 9001:9001
# Visit curl http://localhost:9001 in another console
```

### Monitor Memory
```bash
watch 'free -h && echo && kubectl top pods -n portfolio 2>/dev/null'
```

---

## Scaling Up Later

If you upgrade to a 4GB+ droplet:

```bash
# Scale to 2 replicas for load balancing demo
kubectl scale deployment backend -n portfolio --replicas=2
kubectl scale deployment image-service -n portfolio --replicas=2

# Verify load distribution
kubectl logs -n portfolio -l app=image-service -f --prefix

# Scale Redpanda to a 3-node cluster (requires rebalancing partitions after)
kubectl scale statefulset redpanda -n portfolio --replicas=3
# Then rebalance partition leadership across all brokers:
kubectl exec -n portfolio redpanda-0 -- rpk cluster rebalance
```

---

## 🛠️ Troubleshooting

### OOM Kills
```bash
kubectl get events -n portfolio --sort-by=.lastTimestamp | grep -i oom
free -h
swapon --show
```

### Pod Won't Start
```bash
kubectl describe pod <pod-name> -n portfolio
kubectl logs <pod-name> -n portfolio
```

### Replica Not Syncing
```bash
# Check replication slot exists
kubectl exec -n portfolio postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT slot_name, active FROM pg_replication_slots;"'

# Recreate replica if needed
kubectl delete pod -n portfolio postgres-replica-0
# StatefulSet will auto-recreate and re-sync
```

### Tables Appear Missing (Wrong Schema)
```bash
# All app tables are in the proveo schema, NOT public.
# public only contains alembic_version.
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c "\dt proveo.*"'

# List all schemas
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c "\dn"'
```

### Image Service Not Starting
```bash
# Check if MinIO is accessible
kubectl exec -n portfolio deployment/image-service -- \
  curl http://minio:9000/minio/health/live

# Check NSFW model loading
kubectl logs -n portfolio deployment/image-service | grep -i nsfw
```

### Redpanda Not Starting or Topics Missing
```bash
# Check broker logs for startup errors
kubectl logs -n portfolio redpanda-0 --tail=50

# Verify the StatefulSet is healthy
kubectl describe statefulset redpanda -n portfolio

# If the init Job completed but topics are missing, re-run it manually:
kubectl delete job redpanda-init -n portfolio 2>/dev/null || true
kubectl apply -f k8s/12-redpanda-init.yaml

# Confirm topic creation
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic list --brokers=localhost:9092

# If the backend shows kafka_producer_start_failed in logs,
# check that the broker is reachable from the backend pod:
kubectl exec -n portfolio deployment/backend -- \
  nc -zv redpanda 9092
# Expected: Connection to redpanda 9092 port [tcp/*] succeeded!
```

### Events Not Appearing in Topics
```bash
# Check backend logs for publish errors
kubectl logs -n portfolio deployment/backend | grep -E "kafka_event|kafka_producer"

# Verify PARTITION_MAP keys match what the API sends (es or en only)
# Any other lang value is silently discarded — check for kafka_event_discarded:
kubectl logs -n portfolio deployment/backend | grep "kafka_event_discarded"

# Manually publish a test message to verify the broker accepts writes:
kubectl exec -n portfolio redpanda-0 -- \
  bash -c 'echo "{\"test\":true}" | rpk topic produce user-logins \
  --brokers=localhost:9092 --partition=0'

# Then consume it back:
kubectl exec -n portfolio redpanda-0 -- \
  rpk topic consume user-logins --brokers=localhost:9092 \
  --offset=end --num=1
```

### kubectl Permission Denied
```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
export KUBECONFIG=~/.kube/config
```

### Clean Restart
```bash
./cleanup.sh
./deploy-k3s-local.sh
```

---

## 📋 What's in the Manifests

| File | Description |
|------|-------------|
| `00-namespace.yaml` | Creates `portfolio` namespace |
| `01-configmap.yaml` | App configuration (reduced pool sizes for 2GB) |
| `02-secrets.yaml` | Documentation only — secrets auto-generated by deploy script |
| `03-pvcs.yaml` | Persistent storage (5GB PG, 10GB MinIO, 512MB Redis) |
| `04-postgres-primary.yaml` | **Primary database** — writes, replication source ⭐ |
| `05-postgres-replica.yaml` | **Read replica** — streaming replication ⭐ |
| `06-redis.yaml` | Cache (64MB maxmemory, LRU eviction) |
| `07-minio.yaml` | Object storage for images |
| `08-image-service.yaml` | **NSFW detection service** — TensorFlow model ⭐ |
| `09-backend.yaml` | FastAPI app (1 worker, migrations via initContainer) |
| `10-nginx.yaml` | Reverse proxy, gzip, rate limiting, security headers |
| `11-redpanda.yaml` | **Kafka-compatible event broker** — StatefulSet, persistent storage ⭐ |
| `12-redpanda-init.yaml` | **One-shot Job** — creates topics after broker is confirmed healthy ⭐ |

---

## 🎓 Learning Highlights

1. **StatefulSets**: Used for postgres-primary, postgres-replica, and redpanda (stable network identity, ordered startup, per-replica storage)
2. **Deployments**: Used for stateless services (backend, image-service, nginx)
3. **Jobs**: Used for one-shot configuration tasks (redpanda-init topic creation)
4. **Services**: ClusterIP for internal communication, LoadBalancer for external access
5. **InitContainers**: Wait for dependencies, run migrations, bootstrap replica from primary
6. **ConfigMaps/Secrets**: Separate config from code, auto-generated credentials
7. **PersistentVolumeClaims**: Data survives pod restarts (volumeClaimTemplates for Redpanda)
8. **Liveness/Readiness Probes**: Auto-healing and traffic gating
9. **Resource Limits**: Memory budgeting for constrained environments
10. **Swap Management**: Running production-like workloads on minimal hardware
11. **Explicit partition routing**: Bypassing Kafka key hashing with a direct PARTITION_MAP
12. **Deploy ordering**: StatefulSet wait → Job apply pattern solving the init-container deadlock

---

## 💡 General Notes

- **All features enabled**: NSFW detection, replication, event streaming, caching, runs slow but complete.
- **Self-signed SSL**: PostgreSQL certificates are auto-generated by an initContainer.
- **No external registry**: Custom images are built on-droplet and imported to k3s.
- **Official images**: PostgreSQL, Redis, MinIO, and Redpanda are pulled from their registries automatically.
- **Auto-generated secrets**: Deploy script creates secure passwords and saves them to `.credentials`.
- **Non-root operation**: Scripts use `sudo` only where needed; `kubectl` runs as a regular user.
- **Demo setup**: Optimized to show the full stack on minimal hardware.
- **Schema layout**: All application tables live in the `proveo` schema. `public` only contains `alembic_version`. Always use `proveo.*` when querying tables directly.
- **Node destruction warning / Local-path limitation**:
  - Data is stored on the node's local SSD via `local-path`. If the node is deleted or the SSD fails, the database and Redpanda message logs are lost.
  - For the demo app, the intended strategy is a full restart: run `cleanup.sh` and then `deploy-k3s-local.sh` on a new droplet. Data will be lost, but Alembic migrations recreate the schema and test data can be re-seeded.
  - In production, consider additional durability layers:
    • Scheduled `pg_dump` backups to S3/GCS via a CronJob (e.g., daily)  
    • DigitalOcean Block Storage volumes (replicated storage)  
    • Cross-region replication to standby nodes in other datacenters  
    • Backup services like Barman or pgBackRest that continuously archive WAL to cloud storage
  - Recovery process: provision a new node, install k3s, restore from backup, redeploy.
  - Key insight: `local-path` + single-node = convenient for demos, but **not durable for production**.

## 🔹 Volume / VolumeMount Order (Kubernetes Note)

1. **Volumes (`volumes:`)**  
   - Created or attached **before any container starts**.  
   - This includes **PVCs**, `emptyDir`, and **ConfigMaps**.

2. **VolumeMounts**  
   - Define **per-container mappings** that specify where a volume appears inside that container.  
   - Before a container (initContainer or main) starts, Kubernetes **mounts the volumes at the specified paths**.  
   - This separation explains why Kubernetes requires both `volumes:` (definition) and `volumeMounts:` (container path).

3. **InitContainers**  
   - Run **after volumes exist and are mounted**.  
   - Can read/write to the volumes to prepare data, certificates, or scripts.

4. **Main containers**  
   - Run **after all initContainers complete**.  
   - See whatever initContainers wrote to the volumes.  
   - InitContainers can prepare volumes so main containers start with everything ready.