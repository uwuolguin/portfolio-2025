# Portfolio K8s Demo - PostgreSQL Replica + Load-Balanced Image Service

A minimal Kubernetes (k3s) demo showcasing:
- **PostgreSQL Primary + Read Replica** - Demonstrates database replication
- **2x Image Service Instances** - Shows load balancing with NSFW detection

Everything runs locally on k3s with no external registry needed.

---

## 🚀 Quick Start

```bash
# 1. Build and import images to k3s
./build-and-import-k3s.sh

# 2. Deploy everything
./deploy-k3s-local.sh

# 3. Create admin user
kubectl exec -n portfolio deployment/backend -- \
  python -m scripts.admin.create_admin

# 4. Get access URL
kubectl get svc nginx -n portfolio
# Visit http://<NODE-IP>:<NODEPORT>
```

---

## 🎯 What This Demonstrates

### 1. PostgreSQL Replication
- **Primary (writes)**: All INSERT/UPDATE/DELETE operations
- **Replica (reads)**: All SELECT queries (with fallback to primary)
- Automatic streaming replication with WAL

```bash
# Verify replication is working
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT application_name, state, sync_state FROM pg_stat_replication;"

# Confirm replica is in recovery mode
kubectl exec -n portfolio postgres-replica-0 -- \
  psql -U postgres -d postgres -c \
  "SELECT pg_is_in_recovery();"
# Should return: t (true)
```

### 2. Load-Balanced Image Service
- **2 replicas** running NSFW detection models
- Automatic load distribution via Kubernetes Service
- Each replica processes images independently

```bash
# See both image service instances
kubectl get pods -n portfolio -l app=image-service

# Watch load distribution in logs
kubectl logs -n portfolio -l app=image-service -f --prefix
```

---

## 📐 Architecture

```
┌─────────────┐
│   Nginx     │  <- Single entry point (NodePort)
│ (LoadBalancer)
└──────┬──────┘
       │
   ┌───┴────┬─────────┐
   │        │         │
┌──▼──┐  ┌─▼──────┐  │
│Backend│ │Image   │  │
│ (2x) │ │Service │  │
└──┬──┘  │ (2x)   │  │
   │     └────┬───┘  │
   │          │      │
┌──▼──────────▼──┐ ┌─▼────┐
│PostgreSQL      │ │MinIO │
│ Primary        │ └──────┘
└────┬───────────┘
     │ replication
┌────▼───────────┐ ┌──────┐
│PostgreSQL      │ │Redis │
│ Replica        │ └──────┘
│ (read-only)    │
└────────────────┘
```

**Components:**
- Nginx (1x): Reverse proxy
- Backend (2x): FastAPI app
- **Image Service (2x)**: NSFW detection, load balanced ⭐
- **PostgreSQL Primary (1x)**: Writes ⭐
- **PostgreSQL Replica (1x)**: Reads ⭐
- Redis (1x): Cache
- MinIO (1x): Object storage

---

## 🔧 Common Commands

### View Running Services
```bash
# All pods
kubectl get pods -n portfolio -o wide

# Just the key demo components
kubectl get pods -n portfolio -l 'app in (postgres-primary,postgres-replica,image-service)'
```

### Scale Image Service
```bash
# Scale to 4 replicas to see load balancing
kubectl scale deployment image-service -n portfolio --replicas=4

# Scale back to 2
kubectl scale deployment image-service -n portfolio --replicas=2
```

### Check Database Activity
```bash
# Connect to primary (writes)
kubectl exec -it -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio

# Connect to replica (reads only)
kubectl exec -it -n portfolio postgres-replica-0 -- \
  psql -U postgres -d portfolio

# Check replication lag
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT client_addr, state, replay_lag FROM pg_stat_replication;"
```

### Monitor Logs
```bash
# Backend logs (watch database queries)
kubectl logs -n portfolio deployment/backend -f

# Image service logs (see load distribution)
kubectl logs -n portfolio deployment/image-service -f --all-containers
```

### Access Services
```bash
# Frontend
kubectl get svc nginx -n portfolio
# Visit http://<IP>:<PORT>

# API docs (port-forward)
kubectl port-forward -n portfolio svc/backend 8000:8000
# Visit http://localhost:8000/docs

# MinIO console (port-forward)
kubectl port-forward -n portfolio svc/minio 9001:9001
# Visit http://localhost:9001
```

---

## 🧪 Testing the Demo

### 1. Test Database Replication

```bash
# In one terminal - watch replication status
watch 'kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -tAc \
  "SELECT state, replay_lag FROM pg_stat_replication;"'

# In another terminal - create test data
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "CREATE TABLE demo_test (id serial, data text, created_at timestamp default now());"

kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "INSERT INTO demo_test (data) VALUES ('test1'), ('test2'), ('test3');"

# Verify replica received the data (should see same data)
kubectl exec -n portfolio postgres-replica-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT * FROM demo_test;"
```

### 2. Test Image Service Load Balancing

```bash
# Upload images and watch which pod handles them
kubectl logs -n portfolio -l app=image-service -f --prefix

# Use the API to upload company images - you'll see different pods processing
```

---

## 🛠️ Troubleshooting

### Replica Not Syncing
```bash
# Check replication slot exists
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT slot_name, active FROM pg_replication_slots;"

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

### Database Connection Issues
```bash
# Test primary connectivity
kubectl exec -n portfolio deployment/backend -- \
  pg_isready -h postgres-primary -U postgres

# Test replica connectivity
kubectl exec -n portfolio deployment/backend -- \
  pg_isready -h postgres-replica -U postgres
```

---

## 🧹 Cleanup

```bash
# Remove everything
./cleanup.sh

# Or manually
kubectl delete namespace portfolio
```

---

## 📋 What's in the Manifests

**Kubernetes Resources:**
- `00-namespace.yaml` - Creates `portfolio` namespace
- `01-configmap.yaml` - App configuration
- `02-secrets.yaml` - Credentials (auto-generated by deploy script)
- `03-pvcs.yaml` - Persistent storage claims
- `04-postgres-primary.yaml` - **Primary database** ⭐
- `05-postgres-replica.yaml` - **Read replica** ⭐
- `06-redis.yaml` - Cache
- `07-minio.yaml` - Object storage
- `08-image-service.yaml` - **2x NSFW detection service** ⭐
- `09-backend.yaml` - FastAPI app (2x)
- `10-nginx.yaml` - Load balancer

---

## 💡 Notes

- **Local only**: Uses k3s local-path storage
- **Self-signed SSL**: PostgreSQL uses self-signed certificates
- **No external registry**: Images imported directly to k3s
- **Auto-generated secrets**: Deploy script creates secure passwords
- **Minimal config**: Just enough to demonstrate replication and load balancing

---

## 🎓 Learning Points

1. **StatefulSets**: Used for postgres-primary and postgres-replica (stable network identity)
2. **Deployments**: Used for stateless services (backend, image-service)
3. **Services**: ClusterIP for internal communication, LoadBalancer for external access
4. **InitContainers**: Used to wait for dependencies and run migrations
5. **ConfigMaps/Secrets**: Separate config from code
6. **PersistentVolumeClaims**: Survive pod restarts
7. **Liveness/Readiness Probes**: Auto-healing and zero-downtime deployments

---

**This is a demo setup** - simplified to show PostgreSQL replication and service load balancing in the clearest way possible.