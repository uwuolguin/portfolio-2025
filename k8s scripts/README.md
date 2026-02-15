# Portfolio K8s - DigitalOcean Droplet Deployment

A Kubernetes (k3s) deployment showcasing:
- **PostgreSQL Primary + Read Replica** — Demonstrates database replication
- **Image Service with NSFW Detection** — TensorFlow-based content moderation
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

All scripts run as a **regular user with sudo privileges**  never as root directly.

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
| Swap | None | **2GB** |

---

## 🚀 Quick Start

### 1. Create Droplet & SSH In
```bash
ssh deploy@134.199.211.67
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
http://134.199.211.67/front-page/front-page.html
http://134.199.211.67/docs
http://134.199.211.67/health
```

---

## What Needs sudo vs What Doesn't

| Command | sudo needed? | Why |
|---------|-------------|-----|
| `kubectl ...` | **No** | kubeconfig copied to ~/.kube/config |
| `docker build` | **No** | user added to docker group |
| `sudo k3s ctr images import` | **Yes** | k3s containerd is root-owned |
| Swap/sysctl/apt | **Yes** | system-level operations |

The scripts handle this automatically , you just need a user with sudo access.

---

## 🎯 What This Demonstrates

### 1. PostgreSQL Replication
- **Primary (writes)**: All INSERT/UPDATE/DELETE operations
- **Replica (reads)**: All SELECT queries (with fallback to primary)
- Automatic streaming replication with WAL

```bash
# Verify replication is working
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT application_name, state, sync_state FROM pg_stat_replication;"'

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

### 2. Image Service with NSFW Detection
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
─────────────────────────────────────
Total Requests        ~1388MB
Total Limits          ~2400MB (will use swap)
Available             2048MB RAM + 2048MB swap
```

---

## 🔧 Common Commands

### View Running Services
```bash
# All pods
kubectl get pods -n portfolio -o wide

# Key demo components
kubectl get pods -n portfolio -l 'app in (postgres-primary,postgres-replica,image-service)'
```

### Check Database Activity
```bash
# Connect to primary (writes)
kubectl exec -it -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio'

# Connect to replica (reads only)
# Note: Replica uses official postgres:16 image without .pgpass, so password must be provided explicitly
POSTGRES_PASS=$(kubectl get secret portfolio-secrets -n portfolio -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
kubectl exec -it -n portfolio -c postgres postgres-replica-0 -- \
  bash -c "PGPASSWORD='${POSTGRES_PASS}' psql -U postgres -d portfolio"

# Check replication lag
kubectl exec -n portfolio -c postgres postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT client_addr, state, replay_lag FROM pg_stat_replication;"'
```

### Monitor Logs
```bash
# Backend logs
kubectl logs -n portfolio deployment/backend -f

# Image service logs
kubectl logs -n portfolio deployment/image-service -f
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

## 🧪 Testing the Demo

### 1. Test Database Replication

```bash
# Watch replication status
watch 'kubectl exec -n portfolio postgres-primary-0 -- \
  bash -c "PGPASSWORD=\"\$POSTGRES_PASSWORD\" psql -U postgres -d portfolio -tAc \
  \"SELECT state, replay_lag FROM pg_stat_replication;\""'

# Create test data on primary
kubectl exec -n portfolio postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "CREATE TABLE demo_test (id serial, data text, created_at timestamp default now());"'

kubectl exec -n portfolio postgres-primary-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "INSERT INTO demo_test (data) VALUES ('"'"'test1'"'"'), ('"'"'test2'"'"'), ('"'"'test3'"'"');"'

# Verify replica received the data
kubectl exec -n portfolio postgres-replica-0 -- \
  bash -c 'PGPASSWORD="$POSTGRES_PASSWORD" psql -U postgres -d portfolio -c \
  "SELECT * FROM demo_test;"'
```

### 2. Test Image Upload with NSFW Detection

```bash
# Upload images via the API and watch which pod processes them
kubectl logs -n portfolio deployment/image-service -f
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

### Image Service Not Starting
```bash
# Check if MinIO is accessible
kubectl exec -n portfolio deployment/image-service -- \
  curl http://minio:9000/minio/health/live

# Check NSFW model loading
kubectl logs -n portfolio deployment/image-service | grep -i nsfw
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

---

## 🎓 Learning Highlights

1. **StatefulSets**: Used for postgres-primary and postgres-replica (stable network identity, ordered startup)
2. **Deployments**: Used for stateless services (backend, image-service, nginx)
3. **Services**: ClusterIP for internal communication, LoadBalancer for external access
4. **InitContainers**: Wait for dependencies, run migrations, bootstrap replica from primary
5. **ConfigMaps/Secrets**: Separate config from code, auto-generated credentials
6. **PersistentVolumeClaims**: Data survives pod restarts
7. **Liveness/Readiness Probes**: Auto-healing and traffic gating
8. **Resource Limits**: Memory budgeting for constrained environments
9. **Swap Management**: Running production-like workloads on minimal hardware

---

## 💡 General Notes

- **All features enabled**: NSFW detection, replication, caching, runs slow but complete.
- **Self-signed SSL**: PostgreSQL certificates are auto-generated by an initContainer.
- **No external registry**: Custom images are built on-droplet and imported to k3s.
- **Official images**: PostgreSQL, Redis, and MinIO are pulled from Docker Hub automatically.
- **Auto-generated secrets**: Deploy script creates secure passwords and saves them to `.credentials`.
- **Non-root operation**: Scripts use `sudo` only where needed; `kubectl` runs as a regular user.
- **Demo setup**: Optimized to show the full stack on minimal hardware.
- **Node destruction warning / Local-path limitation**:
  - Data is stored on the node's local SSD via `local-path`. If the node is deleted or the SSD fails, the database is lost.
  - For the demo app, the intended strategy is a full restart: run `cleanup.sh` and then `deploy-k3s-local.sh` on a new droplet. Data will be lost, but Alembic migrations recreate the schema and test data can be re-seeded.
  - In production, consider additional durability layers:
    • Scheduled `pg_dump` backups to S3/GCS via a CronJob (e.g., daily)  
    • DigitalOcean Block Storage volumes (replicated storage)  
    • Cross-region replication to standby nodes in other datacenters  
    • Backup services like Barman or pgBackRest that continuously archive WAL to cloud storage
  - Recovery process: provision a new node, install k3s, restore from backup, redeploy.
  - Key insight: `local-path` + single-node = convenient for demos, but **not durable for production**.

- ## 🔹 Volume / VolumeMount Order (Kubernetes Note)

  1. **Volumes (`volumes:`)**  
     - Created or attached **before any container starts**.  
     - This includes **PVCs**, `emptyDir`, and **ConfigMaps**.

  2. **InitContainers**  
     - Run **after volumes exist**.  
     - Can read/write to the volumes to prepare data, certificates, or scripts.

  3. **Main containers**  
     - Run **after all initContainers complete**.  
     - See whatever initContainers wrote to the volumes.

  4. **VolumeMounts**  
     - Define **per-container mappings** that specify where a volume appears inside that container.  
     - Before a container (initContainer or main) starts, Kubernetes **mounts the volumes at the specified paths**.  
     - This separation explains why Kubernetes requires both `volumes:` (definition) and `volumeMounts:` (container path).  
       InitContainers can prepare volumes so main containers start with everything ready.

`