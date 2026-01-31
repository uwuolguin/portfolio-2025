# 🚀 Proveo - B2B Provider Marketplace Platform

A full-stack marketplace platform connecting businesses with service providers. Built with modern technologies focusing on scalability, security, and performance.

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [🛠️ Tech Stack](#️-tech-stack)
- [🚀 Getting Started](#-getting-started)
- [☸️ Kubernetes Deployment](#️-kubernetes-deployment)
- [📚 API Documentation](#-api-documentation)
- [📁 Project Structure](#-project-structure)
- [🔒 Security Features](#-security-features)
- [⚡ Performance Optimizations](#-performance-optimizations)
- [💻 Development](#-development)
- [🧪 Testing](#-testing)
- [🚢 Deployment](#-deployment)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## ✨ Features

### User Management
- **Email verification system** with automated emails (Resend API)
- **Role-Based Access Control (RBAC)** - Admin and User roles
- **JWT-based authentication** with secure HTTP-only cookies
- **CSRF protection** for all state-changing operations
- **Account self-deletion** with cascading cleanup (soft deletes)

### Company Management
- **One company per user** business rule enforcement
- **Bilingual support** (Spanish/English) with automatic Google Translate API fallback
- **Image upload** with validation, optimization, and NSFW content detection (OpenNSFW2 + TensorFlow)
- **S3-compatible storage** (MinIO) for images
- **Full CRUD operations** with ownership validation
- **Admin company management** with comprehensive audit logging

### Search & Discovery
- **Hybrid search system**:
  - PostgreSQL full-text search (tsvector)
  - Trigram similarity matching (pg_trgm extension)
  - Auto-refreshing materialized views (pg_cron)
- **Multi-filter search** (keywords, location/commune, product category)
- **Pagination support** with configurable limits
- **Language-specific results** (Spanish/English)

### Infrastructure & Operations
- **Database read/write splitting** - Primary for writes, Replica for reads
- **Database connection pooling** with health monitoring and retry logic
- **Redis caching** with graceful degradation when unavailable
- **Rate limiting** (per-IP and global) with Redis-backed counters
- **Structured JSON logging** with correlation IDs for request tracing
- **Docker Compose** for local development
- **Kubernetes (k3s)** for production deployment
- **Automated database migrations** (Alembic)
- **Background job scheduling** (APScheduler) for maintenance tasks

---

## 🏗️ Architecture

### Docker Compose (Development)

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx (Port 80)                       │
│              Reverse Proxy + Static File Server              │
└───────┬─────────────────────────────────┬───────────────────┘
        │                                 │
        │ /api/*                          │ /*
        ↓                                 ↓
┌───────────────────┐           ┌─────────────────────┐
│   FastAPI Backend │           │   Frontend (Static) │
│    (Port 8000)    │           │   HTML/CSS/JS       │
└─────────┬─────────┘           └─────────────────────┘
          │
          ├──────────┬──────────┬──────────┬───────────┐
          ↓          ↓          ↓          ↓           ↓
    ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────┐
    │PostgreSQL│ │ Redis  │ │ MinIO  │ │ Image  │ │pg_cron  │
    │ (DB +   │ │(Cache +│ │ (S3    │ │Service │ │(Mat.View│
    │SSL+Cron)│ │RateLimit│ │Storage)│ │+NSFW)  │ │Refresh) │
    └─────────┘ └────────┘ └────────┘ └────────┘ └─────────┘
```

### Kubernetes (Production)

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
     │ writes/reads     │ writes
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

### Database Read/Write Splitting

The backend implements automatic read/write splitting:

- **Write Operations** (INSERT, UPDATE, DELETE) → `postgres-primary:5432`
- **Read Operations** (SELECT) → `postgres-replica:5432` (with automatic fallback to primary)

```python
# In routers - use appropriate dependency
from app.database.connection import get_db_read, get_db_write

# For READ operations (SELECT)
@router.get("/items")
async def list_items(db = Depends(get_db_read)):
    return await DB.get_all_items(conn=db)

# For WRITE operations (INSERT/UPDATE/DELETE)
@router.post("/items")
async def create_item(db = Depends(get_db_write)):
    return await DB.create_item(conn=db, ...)
```

### Data Flow

1. **Client Request** → Nginx (SSL termination, rate limiting)
2. **Nginx Routes**:
   - `/api/*` → FastAPI Backend
   - `/images/*` → Image Service (proxied)
   - `/*` → Static frontend files
3. **Backend Processing**:
   - JWT validation (HTTP-only cookie)
   - CSRF token validation (for mutations)
   - Redis cache check (products/communes)
   - PostgreSQL query (read from replica, write to primary)
   - Business logic execution
   - Structured logging with correlation ID
4. **Response** → Client with cache headers

---

## 🛠️ Tech Stack

### Backend
- **FastAPI 0.120.0** - Modern async Python web framework
- **asyncpg 0.30.0** - High-performance async PostgreSQL driver
- **Pydantic v2** - Data validation and settings management
- **Alembic 1.17.1** - Database migration management
- **structlog 25.4.0** - Structured JSON logging
- **PyJWT 2.10.1** - JWT token handling
- **bcrypt 5.0.0** - Password hashing (12 rounds)
- **tenacity 9.1.2** - Retry logic with exponential backoff
- **APScheduler 3.10.4** - Background job scheduling

### Database & Storage
- **PostgreSQL 16** with extensions:
  - `pg_trgm` - Trigram similarity search
  - `pg_cron` - Scheduled job execution
  - Full-text search (tsvector/tsquery)
  - Materialized views with concurrent refresh
  - **Streaming replication** (Primary → Replica)
- **MinIO** - S3-compatible object storage for images
- **Redis 7** - In-memory cache and rate limit storage

### Image Processing Service
- **FastAPI** - Dedicated microservice for image operations
- **Pillow 12.0.0** - Image validation, optimization, and conversion
- **OpenCV 4.11.0** - Advanced image processing
- **OpenNSFW2 0.14.0** - AI-powered NSFW content detection
- **TensorFlow 2.15.0** - ML model inference

### Frontend
- **Vanilla JavaScript (ES6+)** - No framework dependencies
- **Component-based architecture** - Modular, reusable components
- **LocalStorage** - Client-side state management
- **Responsive CSS Grid/Flexbox** - Mobile-first design
- **Fetch API** - Modern HTTP client

### DevOps & Infrastructure
- **Docker Compose** - Local development orchestration
- **Kubernetes (k3s)** - Production container orchestration
- **Nginx Alpine** - Lightweight reverse proxy
- **Multi-stage Docker builds** - Optimized image sizes
- **Health checks** - Container-level monitoring
- **SSL/TLS** - PostgreSQL encryption support
- **Git** - Version control

---

## 🚀 Getting Started

### Prerequisites

- **Docker** 24.0+ & **Docker Compose** 2.20+
- **Git** 2.40+
- **4GB RAM** minimum (8GB recommended for NSFW model)
- **10GB disk space** (for Docker images and volumes)
- **Internet connection** (for downloading ML models on first run)

### Quick Start (Docker Compose)

#### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/proveo.git
cd proveo
```

#### 2. Create Environment File
```bash
cp .env.example .env
```

Edit `.env` with your configuration (see full example in `.env.example`)

#### 3. Start the Application
```bash
# Start all containers
docker compose up -d

# View logs
docker compose logs -f
```

#### 4. Initialize the Database & Seed Data
```bash
# Run migrations
docker compose exec backend alembic upgrade head

# Set up pg_cron job for materialized view refresh
docker compose exec backend python -m scripts.database.manage_search_refresh_cron

# Seed test data (16 users with companies + 1 admin)
docker compose exec backend python -m scripts.database.seed_test_data
```

#### 5. Access the Application
- **Frontend**: http://localhost/front-page/front-page.html
- **API Docs (Swagger)**: http://localhost/docs
- **MinIO Console**: http://localhost:9001

#### 6. Test Login Credentials

**Admin Account:**
- Email: `admin_test@mail.com`
- Password: `password`

**Test Users (16 accounts):**
- Email: `testuser01@proveo.com` through `testuser16@proveo.com`
- Password: `TestPass123!`

---

## ☸️ Kubernetes Deployment

### Architecture Overview

The Kubernetes deployment provides:
- **PostgreSQL Primary** (1 instance) - Handles all writes
- **PostgreSQL Replica** (1 instance) - Handles reads with automatic fallback
- **Backend** (2 replicas) - With read/write database splitting
- **Image Service** (2 replicas) - Load balanced
- **Redis** (1 instance) - Caching and rate limiting
- **MinIO** (1 instance) - Object storage
- **Nginx** (1 instance) - LoadBalancer ingress

### Resource Distribution

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

### Prerequisites

1. **k3s installed** on your server
2. **kubectl** configured to access your k3s cluster
3. **Docker images** built and available

### Step 1: Build and Import Docker Images

```bash
# Build images locally
docker build -t portfolio-backend:latest ./backend
docker build -t portfolio-image-service:latest ./image-service
docker build -t portfolio-nginx:latest ./nginx

# Import to k3s
docker save portfolio-backend:latest | sudo k3s ctr images import -
docker save portfolio-image-service:latest | sudo k3s ctr images import -
docker save portfolio-nginx:latest | sudo k3s ctr images import -
```

### Step 2: Deploy with Script

```bash
cd k8s

# Make scripts executable
chmod +x scripts/deploy.sh scripts/cleanup.sh

# Deploy everything (generates secure secrets automatically)
./scripts/deploy.sh

# Or with custom registry prefix
./scripts/deploy.sh your-registry.com/portfolio
```

### Step 3: Manual Deployment (Alternative)

```bash
cd k8s

# Create namespace
kubectl apply -f 00-namespace.yaml

# Create ConfigMap
kubectl apply -f 01-configmap.yaml

# Create secrets (generate secure passwords!)
export POSTGRES_PASSWORD=$(openssl rand -base64 32)
kubectl create secret generic portfolio-secrets \
  --from-literal=POSTGRES_USER=postgres \
  --from-literal=POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  --from-literal=DATABASE_URL="postgresql://postgres:${POSTGRES_PASSWORD}@postgres-primary:5432/portfolio?sslmode=require" \
  --from-literal=DATABASE_URL_PRIMARY="postgresql://postgres:${POSTGRES_PASSWORD}@postgres-primary:5432/portfolio?sslmode=require" \
  --from-literal=DATABASE_URL_REPLICA="postgresql://postgres:${POSTGRES_PASSWORD}@postgres-replica:5432/portfolio?sslmode=require" \
  # ... add other secrets
  -n portfolio

# Create PVCs
kubectl apply -f 03-pvcs.yaml

# Deploy PostgreSQL Primary
kubectl apply -f 04-postgres-primary.yaml
kubectl wait --for=condition=ready pod -l app=postgres-primary -n portfolio --timeout=180s

# Deploy PostgreSQL Replica
kubectl apply -f 05-postgres-replica.yaml
kubectl wait --for=condition=ready pod -l app=postgres-replica -n portfolio --timeout=300s

# Deploy remaining services
kubectl apply -f 06-redis.yaml
kubectl apply -f 07-minio.yaml
kubectl apply -f 08-image-service.yaml
kubectl apply -f 09-backend.yaml
kubectl apply -f 10-nginx.yaml
```

### Step 4: Verify Deployment

```bash
# Check all pods
kubectl get pods -n portfolio

# Verify replication status
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -c "SELECT client_addr, state, sync_state FROM pg_stat_replication;"

# Verify replica is in recovery mode
kubectl exec -n portfolio postgres-replica-0 -- \
  psql -U postgres -c "SELECT pg_is_in_recovery();"
# Should return: t

# Check services
kubectl get svc -n portfolio
```

### Step 5: Initialize Application

```bash
# Create admin user
kubectl exec -n portfolio deployment/backend -- \
  python -m scripts.admin.create_admin

# Seed test data (optional)
kubectl exec -n portfolio deployment/backend -- \
  python -m scripts.database.seed_test_data
```

### Scaling

```bash
# Scale backend (horizontal)
kubectl scale deployment backend -n portfolio --replicas=5

# Scale image service
kubectl scale deployment image-service -n portfolio --replicas=4

# NOTE: Don't scale PostgreSQL without proper cluster setup
```

### Monitoring

```bash
# View logs
kubectl logs -n portfolio deployment/backend -f
kubectl logs -n portfolio deployment/image-service -f

# Check resource usage
kubectl top pods -n portfolio

# Check replication lag
kubectl exec -n portfolio postgres-primary-0 -- \
  psql -U postgres -c "SELECT client_addr, sent_lsn, replay_lsn, replay_lag FROM pg_stat_replication;"
```

### Database Operations

```bash
# Connect to Primary (for writes)
kubectl exec -it -n portfolio postgres-primary-0 -- psql -U postgres -d portfolio

# Connect to Replica (for reads)
kubectl exec -it -n portfolio postgres-replica-0 -- psql -U postgres -d portfolio

# Backup database
kubectl exec -n portfolio postgres-primary-0 -- \
  pg_dump -U postgres portfolio > backup-$(date +%Y%m%d).sql
```

### Cleanup

```bash
# Delete everything
./scripts/cleanup.sh

# Or manually
kubectl delete namespace portfolio
```

### Kubernetes Files Structure

```
k8s/
├── 00-namespace.yaml          # portfolio namespace
├── 01-configmap.yaml          # Application configuration
├── 02-secrets.yaml            # Credentials (template only)
├── 03-pvcs.yaml               # Persistent Volume Claims
├── 04-postgres-primary.yaml   # PostgreSQL Primary StatefulSet
├── 05-postgres-replica.yaml   # PostgreSQL Replica StatefulSet
├── 06-redis.yaml              # Redis Deployment
├── 07-minio.yaml              # MinIO Deployment
├── 08-image-service.yaml      # Image Service (2 replicas)
├── 09-backend.yaml            # Backend (2 replicas)
├── 10-nginx.yaml              # Nginx LoadBalancer
└── scripts/
    ├── deploy.sh              # Automated deployment script
    └── cleanup.sh             # Cleanup script
```

---

## 📚 API Documentation

### Interactive Documentation
- **Swagger UI**: http://localhost/docs (recommended)
- **ReDoc**: http://localhost/redoc

### Authentication Flow

```
Client                API                 DB                  Email
  │                    │                   │                    │
  ├─POST /signup──────>│                   │                    │
  │                    ├─Create user (PRIMARY)─>│               │
  │                    │                   │                    │
  │                    ├─Send verification email───────────────>│
  │<───201 Created─────┤                   │                    │
  │                    │                   │                    │
  ├─GET /verify/{token}│                   │                    │
  │                    ├─Update verified (PRIMARY)─>│           │
  │<───HTML success────┤                   │                    │
  │                    │                   │                    │
  ├─POST /login───────>│                   │                    │
  │                    ├─Verify creds (PRIMARY)─>│              │
  │<───JWT+CSRF─────────┤                   │                    │
  │                    │                   │                    │
  ├─GET /companies/search─>│               │                    │
  │                    ├─Query (REPLICA)───>│                   │
  │<───200 Results─────┤                   │                    │
  │                    │                   │                    │
  ├─POST /companies───>│                   │                    │
  │ (with CSRF header) │                   │                    │
  │                    ├─Create company (PRIMARY)─>│            │
  │<───201 Created─────┤                   │                    │
```

### Key Endpoints

#### Authentication & User Management
```http
POST   /api/v1/users/signup                    # Register (WRITE)
GET    /api/v1/users/verify-email/{token}      # Verify email (WRITE)
POST   /api/v1/users/resend-verification       # Resend verification (WRITE)
POST   /api/v1/users/login                     # Login (WRITE)
POST   /api/v1/users/logout                    # Logout
GET    /api/v1/users/me                        # Get current user (JWT only)
DELETE /api/v1/users/me                        # Delete own account (WRITE)
```

#### Companies
```http
GET    /api/v1/companies/search                # Search companies (READ - uses replica)
GET    /api/v1/companies/{uuid}                # Get company (READ - uses replica)
GET    /api/v1/companies/user/my-company       # Get my company (READ - uses replica)
POST   /api/v1/companies                       # Create company (WRITE - uses primary)
PATCH  /api/v1/companies/user/my-company       # Update company (WRITE - uses primary)
DELETE /api/v1/companies/user/my-company       # Delete company (WRITE - uses primary)
```

#### Products & Communes
```http
GET    /api/v1/products/                       # List products (READ - uses replica)
GET    /api/v1/communes/                       # List communes (READ - uses replica)
```

#### Health Checks
```http
GET    /api/v1/health/                         # Basic health check
GET    /api/v1/health/database                 # Database health (shows pool stats)
```

---

## 📁 Project Structure

```
proveo/
├── backend/
│   ├── app/
│   │   ├── database/
│   │   │   ├── connection.py         # Read/Write pool manager
│   │   │   ├── transactions.py       # DB operations with readonly flags
│   │   │   └── db_retry.py           # Retry logic
│   │   ├── routers/
│   │   │   ├── users.py              # get_db_read / get_db_write
│   │   │   ├── companies.py          # get_db_read / get_db_write
│   │   │   ├── products.py           # get_db_read / get_db_write
│   │   │   ├── communes.py           # get_db_read / get_db_write
│   │   │   └── health.py             # get_db_read
│   │   └── ...
│   └── ...
│
├── k8s/                              # Kubernetes manifests
│   ├── 00-namespace.yaml
│   ├── 01-configmap.yaml
│   ├── 02-secrets.yaml
│   ├── 03-pvcs.yaml
│   ├── 04-postgres-primary.yaml      # Primary with replication
│   ├── 05-postgres-replica.yaml      # Replica with streaming replication
│   ├── 06-redis.yaml
│   ├── 07-minio.yaml
│   ├── 08-image-service.yaml         # 2 replicas
│   ├── 09-backend.yaml               # 2 replicas with DB splitting
│   ├── 10-nginx.yaml
│   └── scripts/
│       ├── deploy.sh
│       └── cleanup.sh
│
├── docker-compose.yml                # Local development
└── README.md
```

---

## 🔒 Security Features

### Authentication & Authorization
- **JWT tokens** stored in HTTP-only cookies (XSS protection)
- **CSRF tokens** required for all mutations
- **bcrypt password hashing** with 12 rounds
- **Email verification** before account activation
- **Role-Based Access Control** (User/Admin)

### Database Security
- **SSL/TLS encryption** for PostgreSQL connections
- **Parameterized queries** (SQL injection prevention)
- **Connection pooling** with health monitoring
- **Automatic failover** (replica → primary for reads)

### Infrastructure Security
- **Security headers** (CSP, HSTS, X-Frame-Options)
- **Rate limiting** (Redis-backed)
- **CORS** with explicit origin whitelist
- **Network policies** (Kubernetes)

---

## ⚡ Performance Optimizations

### Database Layer
- **Read/Write splitting** - Offload reads to replica
- **asyncpg connection pooling** (5-20 connections)
- **Materialized views** with pg_cron refresh
- **Retry logic** with exponential backoff

### Caching Strategy
- **Redis caching** for products/communes (3-day TTL)
- **Graceful degradation** when Redis unavailable
- **Cache invalidation** on create/update/delete

### Kubernetes
- **Horizontal scaling** for backend and image service
- **Resource limits** and requests
- **Health checks** (liveness/readiness probes)
- **Rolling updates** with zero downtime

---

## 💻 Development

### Local Development (Docker Compose)
```bash
docker compose up -d
docker compose logs -f backend
```

### Database Migrations
```bash
# Docker Compose
docker compose exec backend alembic upgrade head

# Kubernetes
kubectl exec -n portfolio deployment/backend -- alembic upgrade head
```

### Useful Commands
```bash
# View container logs
docker compose logs -f [service_name]

# Access database (Docker)
docker compose exec postgres psql -U postgres -d portfolio

# Access database (Kubernetes - Primary)
kubectl exec -it -n portfolio postgres-primary-0 -- psql -U postgres -d portfolio

# Access database (Kubernetes - Replica)
kubectl exec -it -n portfolio postgres-replica-0 -- psql -U postgres -d portfolio
```

---

## 🧪 Testing

```bash
# Run all tests
docker compose exec backend pytest app/tests/ -v

# Run with coverage
docker compose exec backend pytest app/tests/ --cov=app --cov-report=html
```

---

## 🚢 Deployment

### Production Checklist

#### Security
- [ ] **Remove CSRF admin bypass** from `backend/app/auth/csrf.py`
- [ ] **Change all default passwords**
- [ ] **Generate secure SECRET_KEY**: `openssl rand -hex 32`
- [ ] **Set DEBUG=false**
- [ ] **Enable HTTPS/TLS** with valid certificates
- [ ] **Review CORS configuration**

#### Infrastructure
- [ ] **Configure SSL certificates** (nginx + PostgreSQL)
- [ ] **Set up monitoring** (health checks, metrics)
- [ ] **Configure log aggregation**
- [ ] **Set up backup strategy** (PostgreSQL, MinIO)
- [ ] **Test database failover**

---

## 🗺️ Roadmap

### Completed ✅
- [x] User authentication with email verification
- [x] Company CRUD with image uploads
- [x] Search with materialized views
- [x] NSFW content detection
- [x] Docker Compose development environment
- [x] **Kubernetes (k3s) deployment**
- [x] **PostgreSQL read/write splitting**
- [x] **Database replication (Primary → Replica)**

### In Progress 🚧
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Monitoring dashboard (Prometheus + Grafana)
- [ ] Automated backups

### Future
- [ ] Horizontal Pod Autoscaler (HPA)
- [ ] Redis Sentinel (high availability)
- [ ] CDN integration
- [ ] Elasticsearch for advanced search

---

## 📄 License

This project is for portfolio demonstration purposes only.

---

> ⚠️ **CRITICAL SECURITY WARNING FOR PRODUCTION DEPLOYMENT** ⚠️
> 
> **This codebase contains an admin CSRF bypass mechanism for development/testing purposes that MUST be removed before any production deployment.**
>
> **Location**: `backend/app/auth/csrf.py`
>
> **Before production**:
> 1. Remove the entire admin bypass block from `validate_csrf_token()`
> 2. Remove all references to `ADMIN_BYPASS_IPS` and `admin_api_key`
> 3. Remove `/use-postman-or-similar-to-bypass-csrf` endpoints

---

**Built with ❤️ as a portfolio project**

**Last Updated**: January 2026