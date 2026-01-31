# Kubernetes (k3s) Deployment Guide

## Architecture Overview

- **PostgreSQL**: 1 primary (writes) + 1 replica (reads)
- **Image Service**: 2 replicas with load balancing
- **Backend**: 2 replicas
- **Redis**: 1 instance
- **MinIO**: 1 instance
- **Nginx**: 1 instance (LoadBalancer)

## Prerequisites

1. **k3s installed** on your server
2. **kubectl** configured to access your k3s cluster
3. **Docker images** built and pushed to a registry (or use local images)
4. **Storage**: k3s local-path provisioner (default)

## Step 1: Build and Push Docker Images

### Option A: Push to Container Registry (Recommended)

```bash
# Login to your registry
docker login your-registry.com

# Build and push backend
cd backend
docker build -t your-registry.com/portfolio-backend:latest .
docker push your-registry.com/portfolio-backend:latest

# Build and push image-service
cd ../image-service
docker build -t your-registry.com/portfolio-image-service:latest .
docker push your-registry.com/portfolio-image-service:latest

# Build and push nginx (with frontend static files)
cd ../nginx
docker build -t your-registry.com/portfolio-nginx:latest .
docker push your-registry.com/portfolio-nginx:latest
```

### Option B: Use k3s Local Images (Testing Only)

```bash
# Import images directly to k3s
docker save portfolio-backend:latest | sudo k3s ctr images import -
docker save portfolio-image-service:latest | sudo k3s ctr images import -
docker save portfolio-nginx:latest | sudo k3s ctr images import -
```

## Step 2: Update Image References

Edit these files and replace `your-registry` with your actual registry:

- `k8s/08-image-service.yaml` (line 32)
- `k8s/09-backend.yaml` (lines 39, 67)
- `k8s/10-nginx.yaml` (line 186)

```bash
# Quick replace (adjust registry name)
cd k8s
sed -i 's|your-registry/|registry.example.com/portfolio-|g' *.yaml
```

## Step 3: Configure Secrets

**CRITICAL**: Generate secure secrets before deployment!

```bash
# Generate secrets
export POSTGRES_PASSWORD=$(openssl rand -base64 32)
export JWT_SECRET=$(openssl rand -base64 32)
export ADMIN_API_KEY=$(openssl rand -base64 32)
export MINIO_PASSWORD=$(openssl rand -base64 32)

# Create secrets
kubectl create namespace portfolio

kubectl create secret generic portfolio-secrets \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=DATABASE_URL="postgresql://postgres:$POSTGRES_PASSWORD@postgres-primary:5432/portfolio?sslmode=require" \
  --from-literal=ALEMBIC_DATABASE_URL="postgresql://postgres:$POSTGRES_PASSWORD@postgres-primary:5432/portfolio?sslmode=require" \
  --from-literal=REDIS_URL="redis://redis:6379/0" \
  --from-literal=MINIO_ROOT_USER=minioadmin \
  --from-literal=MINIO_ROOT_PASSWORD="$MINIO_PASSWORD" \
  --from-literal=SECRET_KEY="$JWT_SECRET" \
  --from-literal=ADMIN_API_KEY="$ADMIN_API_KEY" \
  --from-literal=ADMIN_BYPASS_IPS="10.0.0.0/8,172.16.0.0/12,192.168.0.0/16" \
  --from-literal=RESEND_API_KEY="re_YOUR_KEY_HERE" \
  --from-literal=ADMIN_EMAIL="admin@example.com" \
  --from-literal=API_BASE_URL="http://your-domain.com" \
  -n portfolio

# Save credentials securely
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" > .credentials
echo "JWT_SECRET=$JWT_SECRET" >> .credentials
echo "ADMIN_API_KEY=$ADMIN_API_KEY" >> .credentials
echo "MINIO_PASSWORD=$MINIO_PASSWORD" >> .credentials
chmod 600 .credentials
```

## Step 4: Deploy to Kubernetes

```bash
cd k8s

# Apply in order
kubectl apply -f 00-namespace.yaml
kubectl apply -f 01-configmap.yaml
# Skip 02-secrets.yaml (created manually above)
kubectl apply -f 03-pvcs.yaml
kubectl apply -f 04-postgres-primary.yaml

# Wait for primary to be ready
kubectl wait --for=condition=ready pod -l app=postgres-primary -n portfolio --timeout=120s

# Create replication slot on primary
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT pg_create_physical_replication_slot('replica_slot_1');"

# Deploy replica
kubectl apply -f 05-postgres-replica.yaml
kubectl wait --for=condition=ready pod -l app=postgres-replica -n portfolio --timeout=180s

# Deploy remaining services
kubectl apply -f 06-redis.yaml
kubectl apply -f 07-minio.yaml
kubectl apply -f 08-image-service.yaml
kubectl apply -f 09-backend.yaml
kubectl apply -f 10-nginx.yaml
```

## Step 5: Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n portfolio

# Check services
kubectl get svc -n portfolio

# Check replica status
kubectl exec -n portfolio postgres-replica-0 -- \
  psql -U postgres -d postgres -c "SELECT pg_is_in_recovery();"
# Should return: t (true)

# Check replication lag
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT client_addr, state, sync_state, replay_lag FROM pg_stat_replication;"
```

## Step 6: Access the Application

```bash
# Get LoadBalancer IP (k3s ServiceLB)
kubectl get svc nginx -n portfolio -o jsonpath='{.status.loadBalancer.ingress[0].ip}'

# Access via:
# http://<LOADBALANCER_IP>/
```

## Step 7: Initialize Database and Create Admin

```bash
# The init container in backend deployment runs migrations automatically
# Create admin user manually:

kubectl exec -n portfolio deployment/backend -- \
  python -m scripts.admin.create_admin

# Follow prompts to create admin account
```

## Step 8: Seed Test Data (Optional)

```bash
kubectl exec -n portfolio deployment/backend -- \
  python -m scripts.database.seed_test_data
```

## Traffic Management

### Scale Image Service

```bash
# Scale to 3 replicas
kubectl scale deployment image-service -n portfolio --replicas=3

# Scale down to 1
kubectl scale deployment image-service -n portfolio --replicas=1
```

### Scale Backend

```bash
kubectl scale deployment backend -n portfolio --replicas=3
```

### View Traffic Distribution

```bash
# Check image-service endpoints
kubectl get endpoints image-service -n portfolio

# Watch pod resource usage
kubectl top pods -n portfolio
```

## Monitoring

```bash
# View logs
kubectl logs -n portfolio deployment/backend -f
kubectl logs -n portfolio deployment/image-service -f

# Check resource usage
kubectl top pods -n portfolio
kubectl top nodes

# Describe problematic pods
kubectl describe pod -n portfolio <pod-name>
```

## Database Operations

### Connect to Primary (Writes)

```bash
kubectl exec -it -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio
```

### Connect to Replica (Reads)

```bash
kubectl exec -it -n portfolio postgres-replica-0 -- \
  psql -U postgres -d portfolio
```

### Backup Database

```bash
kubectl exec -n portfolio postgres-primary-0 -- \
  pg_dump -U postgres portfolio > backup-$(date +%Y%m%d).sql
```

### Check Replication Status

```bash
# On primary
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT * FROM pg_stat_replication;"

# On replica
kubectl exec -n portfolio postgres-replica-0 -- \
  psql -U postgres -d postgres -c \
  "SELECT pg_last_wal_receive_lsn(), pg_last_wal_replay_lsn(), pg_last_xact_replay_timestamp();"
```

## Troubleshooting

### Pods Not Starting

```bash
# Check events
kubectl get events -n portfolio --sort-by='.lastTimestamp'

# Check pod details
kubectl describe pod -n portfolio <pod-name>

# Check logs
kubectl logs -n portfolio <pod-name> --previous
```

### Replica Not Syncing

```bash
# Check replica logs
kubectl logs -n portfolio postgres-replica-0

# Reinitialize replica
kubectl delete pod -n portfolio postgres-replica-0
# It will recreate and re-sync from primary
```

### Image Service Connection Issues

```bash
# Check if MinIO is accessible
kubectl exec -n portfolio deployment/image-service -- \
  curl -f http://minio:9000/minio/health/live
```

### Backend Database Connection Issues

```bash
# Check if postgres-primary is accessible
kubectl exec -n portfolio deployment/backend -- \
  pg_isready -h postgres-primary -U postgres

# Check secrets
kubectl get secret portfolio-secrets -n portfolio -o yaml
```

## Cleanup

```bash
# Delete everything
kubectl delete namespace portfolio

# Delete PVCs (data will be lost!)
kubectl delete pvc -n portfolio --all
```

## Production Considerations

1. **Remove ADMIN_BYPASS logic** from `backend/app/auth/csrf.py` before production
2. **Enable HTTPS** with cert-manager and Let's Encrypt
3. **Set up monitoring** (Prometheus + Grafana)
4. **Configure backups** for PostgreSQL and MinIO
5. **Use external secrets** (Sealed Secrets, External Secrets Operator)
6. **Resource limits** - adjust based on load testing
7. **HPA** - Configure Horizontal Pod Autoscaler for backend/image-service
8. **Persistent storage** - Use proper StorageClass (not local-path) in production
9. **Network policies** - Restrict pod-to-pod communication
10. **Update strategy** - Configure blue-green or canary deployments

## Quick Commands Reference

```bash
# Watch all pods
kubectl get pods -n portfolio -w

# Restart backend
kubectl rollout restart deployment/backend -n portfolio

# Scale image-service to 5 replicas
kubectl scale deployment image-service -n portfolio --replicas=5

# Port-forward to access services locally
kubectl port-forward -n portfolio svc/nginx 8080:80
kubectl port-forward -n portfolio svc/minio 9001:9001  # MinIO console

# Get all resources
kubectl get all -n portfolio

# Check disk usage
kubectl exec -n portfolio postgres-primary-0 -- df -h
```