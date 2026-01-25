#!/bin/bash
set -e

# Quick deployment script for k3s
# Usage: ./deploy.sh [registry-prefix]
# Example: ./deploy.sh registry.example.com/portfolio

REGISTRY_PREFIX="${1:-your-registry}"

echo "=================================="
echo "Portfolio k3s Deployment Script"
echo "=================================="
echo ""
echo "Registry prefix: $REGISTRY_PREFIX"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found${NC}"
    exit 1
fi

if ! command -v openssl &> /dev/null; then
    echo -e "${RED}Error: openssl not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo ""

# Update image references
echo "Updating image references in manifests..."
cd k8s
for file in 08-image-service.yaml 09-backend.yaml 10-nginx.yaml; do
    if [ -f "$file" ]; then
        sed -i.bak "s|your-registry/|${REGISTRY_PREFIX}/|g" "$file"
        echo "  ✓ Updated $file"
    fi
done
cd ..
echo ""

# Generate secrets
echo "Generating secure secrets..."
POSTGRES_PASSWORD=$(openssl rand -base64 32)
JWT_SECRET=$(openssl rand -base64 32)
ADMIN_API_KEY=$(openssl rand -base64 32)
MINIO_PASSWORD=$(openssl rand -base64 32)

echo -e "${GREEN}✓ Secrets generated${NC}"
echo ""

# Create namespace
echo "Creating namespace..."
kubectl apply -f k8s/00-namespace.yaml
echo ""

# Create ConfigMap
echo "Creating ConfigMap..."
kubectl apply -f k8s/01-configmap.yaml
echo ""

# Create secrets
echo "Creating secrets..."
kubectl create secret generic portfolio-secrets \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@postgres-primary:5432/portfolio?sslmode=require" \
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

# Save credentials
cat > .credentials <<EOF
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
JWT_SECRET=$JWT_SECRET
ADMIN_API_KEY=$ADMIN_API_KEY
MINIO_PASSWORD=$MINIO_PASSWORD
EOF
chmod 600 .credentials

echo -e "${GREEN}✓ Secrets saved to .credentials${NC}"
echo -e "${YELLOW}⚠  Keep .credentials file secure!${NC}"
echo ""

# Create PVCs
echo "Creating Persistent Volume Claims..."
kubectl apply -f k8s/03-pvcs.yaml
echo ""

# Deploy PostgreSQL Primary
echo "Deploying PostgreSQL Primary..."
kubectl apply -f k8s/04-postgres-primary.yaml

echo "Waiting for PostgreSQL Primary to be ready (max 2 minutes)..."
kubectl wait --for=condition=ready pod -l app=postgres-primary -n portfolio --timeout=120s

echo -e "${GREEN}✓ PostgreSQL Primary ready${NC}"
echo ""

# Create replication slot
echo "Creating replication slot..."
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -d portfolio -c \
  "SELECT pg_create_physical_replication_slot('replica_slot_1');" || echo "Slot may already exist"
echo ""

# Deploy PostgreSQL Replica
echo "Deploying PostgreSQL Replica..."
kubectl apply -f k8s/05-postgres-replica.yaml

echo "Waiting for PostgreSQL Replica to be ready (max 3 minutes)..."
kubectl wait --for=condition=ready pod -l app=postgres-replica -n portfolio --timeout=180s

echo -e "${GREEN}✓ PostgreSQL Replica ready${NC}"
echo ""

# Deploy other services
echo "Deploying Redis..."
kubectl apply -f k8s/06-redis.yaml
kubectl wait --for=condition=ready pod -l app=redis -n portfolio --timeout=60s
echo -e "${GREEN}✓ Redis ready${NC}"
echo ""

echo "Deploying MinIO..."
kubectl apply -f k8s/07-minio.yaml
kubectl wait --for=condition=ready pod -l app=minio -n portfolio --timeout=60s
echo -e "${GREEN}✓ MinIO ready${NC}"
echo ""

echo "Deploying Image Service (2 replicas)..."
kubectl apply -f k8s/08-image-service.yaml
kubectl wait --for=condition=ready pod -l app=image-service -n portfolio --timeout=120s
echo -e "${GREEN}✓ Image Service ready${NC}"
echo ""

echo "Deploying Backend (2 replicas)..."
kubectl apply -f k8s/09-backend.yaml
kubectl wait --for=condition=ready pod -l app=backend -n portfolio --timeout=120s
echo -e "${GREEN}✓ Backend ready${NC}"
echo ""

echo "Deploying Nginx..."
kubectl apply -f k8s/10-nginx.yaml
kubectl wait --for=condition=ready pod -l app=nginx -n portfolio --timeout=60s
echo -e "${GREEN}✓ Nginx ready${NC}"
echo ""

# Summary
echo "=================================="
echo "Deployment Complete!"
echo "=================================="
echo ""
echo "All services are running. Summary:"
echo ""
kubectl get pods -n portfolio
echo ""
echo "Access the application:"
echo ""
LOADBALANCER_IP=$(kubectl get svc nginx -n portfolio -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending...")
echo "  URL: http://$LOADBALANCER_IP"
echo ""
echo "Next steps:"
echo "  1. Create admin user:"
echo "     kubectl exec -n portfolio deployment/backend -- python -m scripts.admin.create_admin"
echo ""
echo "  2. Seed test data (optional):"
echo "     kubectl exec -n portfolio deployment/backend -- python -m scripts.database.seed_test_data"
echo ""
echo "  3. Check replication status:"
echo "     kubectl exec -n portfolio postgres-primary-0 -- psql -U postgres -d portfolio -c 'SELECT * FROM pg_stat_replication;'"
echo ""
echo "Credentials saved in: .credentials"
echo ""