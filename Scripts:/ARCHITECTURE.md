# Portfolio k3s Architecture

## Service Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         Load Balancer                           │
│                      (k3s ServiceLB - nginx)                    │
│                         Port 80 → Nginx                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┴────────────────┐
           │                                │
           ▼                                ▼
    ┌──────────┐                    ┌──────────────┐
    │  Nginx   │                    │   Static     │
    │  Proxy   │──────proxy────────▶│   Files      │
    │  (1x)    │                    │  (frontend)  │
    └────┬─────┘                    └──────────────┘
         │
    ┌────┴──────────────┬──────────────────┐
    │                   │                  │
    ▼                   ▼                  ▼
┌─────────┐      ┌─────────────┐   ┌──────────┐
│ Backend │      │Image Service│   │ /images/ │
│ (2x)    │      │   (2x)      │   │  Route   │
└────┬────┘      └──────┬──────┘   └──────────┘
     │                  │
     │ writes           │ writes
     ▼                  ▼
┌─────────────┐    ┌─────────┐
│ PostgreSQL  │    │  MinIO  │
│   Primary   │    │  (1x)   │
│   (1x)      │    └─────────┘
└──────┬──────┘
       │ replication
       ▼
┌─────────────┐    ┌─────────┐
│ PostgreSQL  │    │  Redis  │
│   Replica   │    │  (1x)   │
│   (1x)      │    └─────────┘
└─────────────┘
    (reads)
```

## Resource Distribution

| Service           | Replicas | CPU Request | Memory Request | Storage |
|-------------------|----------|-------------|----------------|---------|
| Nginx             | 1        | 100m        | 128Mi          | -       |
| Backend           | 2        | 250m        | 512Mi          | -       |
| Image Service     | 2        | 500m        | 1Gi            | -       |
| PostgreSQL Primary| 1        | 500m        | 512Mi          | 10Gi    |
| PostgreSQL Replica| 1        | 250m        | 512Mi          | 10Gi    |
| Redis             | 1        | 100m        | 128Mi          | 1Gi     |
| MinIO             | 1        | 250m        | 256Mi          | 20Gi    |
| **Total**         | **9**    | **2.2 CPU** | **4.5Gi RAM**  | **41Gi**|

## Traffic Flow

### Read Operations (GET requests)
```
Client → Nginx → Backend (2x) → PostgreSQL Replica (read-only)
                              ↘ Redis (cache)
```

### Write Operations (POST/PUT/DELETE)
```
Client → Nginx → Backend (2x) → PostgreSQL Primary (writes)
                              ↘ Redis (invalidate cache)
```

### Image Upload/Download
```
Upload:   Client → Nginx → Image Service (2x) → MinIO
Download: Client → Nginx → Image Service (2x) → MinIO
```

## Scaling Capabilities

### Horizontal Scaling (Add Replicas)
```bash
# Scale backend
kubectl scale deployment backend -n portfolio --replicas=5

# Scale image service
kubectl scale deployment image-service -n portfolio --replicas=4

# NOTE: PostgreSQL and Redis are stateful - don't scale without proper setup
# MinIO would need distributed mode for multiple replicas
```

### Vertical Scaling (Increase Resources)
```bash
# Edit deployment and increase resources
kubectl edit deployment backend -n portfolio

# Or patch directly
kubectl patch deployment backend -n portfolio -p \
  '{"spec":{"template":{"spec":{"containers":[{"name":"backend","resources":{"limits":{"cpu":"2000m","memory":"4Gi"}}}]}}}}'
```

## High Availability Features

✓ **Backend**: 2 replicas with rolling updates
✓ **Image Service**: 2 replicas with load balancing
✓ **Database**: Primary + Replica (read scaling)
✓ **Automatic restarts**: Liveness/readiness probes
✓ **Persistent data**: All stateful services use PVCs
✓ **SSL**: PostgreSQL with SSL/TLS encryption
✓ **Health checks**: All services monitored

## Database Strategy

### Primary (postgres-primary:5432)
- Handles all writes
- Handles reads when replica is unavailable
- WAL streaming to replica
- Replication slot: replica_slot_1

### Replica (postgres-replica:5432)
- Handles read-only queries
- Continuously syncs from primary
- Hot standby mode
- Can be promoted to primary if needed

### Backend Configuration
Currently, the backend uses primary for both reads and writes. To enable read replica usage:

1. Modify backend connection pool configuration
2. Add read-only connection string pointing to replica
3. Route SELECT queries to replica
4. Keep writes on primary

## Load Balancing

### k3s ServiceLB (Default)
- Automatic LoadBalancer for nginx service
- Uses node IP + port forwarding
- Works out of the box

### Alternative: Use Ingress
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: portfolio-ingress
  namespace: portfolio
spec:
  rules:
  - host: portfolio.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nginx
            port:
              number: 80
```

## Monitoring Setup (Optional)

### Prometheus + Grafana
```bash
# Install Prometheus Operator
kubectl apply -f https://raw.githubusercontent.com/prometheus-operator/prometheus-operator/main/bundle.yaml

# Create ServiceMonitor for backend
kubectl apply -f - <<EOF
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: backend-metrics
  namespace: portfolio
spec:
  selector:
    matchLabels:
      app: backend
  endpoints:
  - port: http
    path: /metrics
EOF
```

## Backup Strategy

### PostgreSQL Backup (Recommended: pgBackRest or Velero)
```bash
# Manual backup
kubectl exec -n portfolio postgres-primary-0 -- \
  pg_dump -U postgres portfolio | gzip > backup-$(date +%Y%m%d-%H%M%S).sql.gz

# Automated with CronJob
kubectl apply -f - <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: postgres-backup
  namespace: portfolio
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: postgres:16-alpine
            env:
            - name: PGPASSWORD
              valueFrom:
                secretKeyRef:
                  name: portfolio-secrets
                  key: POSTGRES_PASSWORD
            command:
            - sh
            - -c
            - |
              pg_dump -h postgres-primary -U postgres portfolio | \
              gzip > /backup/portfolio-\$(date +%Y%m%d-%H%M%S).sql.gz
            volumeMounts:
            - name: backup
              mountPath: /backup
          restartPolicy: OnFailure
          volumes:
          - name: backup
            persistentVolumeClaim:
              claimName: postgres-backups
EOF
```

### MinIO Backup
```bash
# Use mc (MinIO Client) to sync to another bucket/S3
kubectl run -n portfolio minio-backup --rm -it --restart=Never \
  --image=minio/mc -- \
  mirror minio-local/images s3-backup/images
```

## Disaster Recovery

### Promote Replica to Primary
```bash
# 1. Stop all backend pods
kubectl scale deployment backend -n portfolio --replicas=0

# 2. Promote replica
kubectl exec -n portfolio postgres-replica-0 -- \
  psql -U postgres -c "SELECT pg_promote();"

# 3. Update backend to use new primary
kubectl set env deployment/backend -n portfolio \
  DATABASE_URL="postgresql://postgres:PASSWORD@postgres-replica:5432/portfolio?sslmode=require"

# 4. Restart backend
kubectl scale deployment backend -n portfolio --replicas=2
```

## Security Checklist

- [ ] Remove ADMIN_BYPASS_IPS logic from backend code
- [ ] Generate strong, unique passwords for all services
- [ ] Enable HTTPS with cert-manager + Let's Encrypt
- [ ] Restrict network policies between pods
- [ ] Enable Pod Security Standards
- [ ] Rotate secrets regularly
- [ ] Enable audit logging
- [ ] Use private container registry
- [ ] Scan images for vulnerabilities
- [ ] Enable RBAC for kubectl access

## Performance Tuning

### Backend Optimization
- Increase connection pool: `DB_POOL_MAX_SIZE=50`
- Tune worker processes: `--workers 4` in uvicorn
- Enable Redis caching aggressively

### PostgreSQL Tuning
```sql
-- Increase shared_buffers
ALTER SYSTEM SET shared_buffers = '512MB';

-- Increase work_mem for complex queries
ALTER SYSTEM SET work_mem = '16MB';

-- Reload configuration
SELECT pg_reload_conf();
```

### Image Service Optimization
- Pre-warm NSFW model cache
- Increase worker threads
- Use CDN for static image delivery