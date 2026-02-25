# 🚀 Proveo - B2B Provider Marketplace Platform

**Overview**: A production-grade full-stack marketplace platform demonstrating modern cloud-native architecture, database replication, microservices, and scalable deployment patterns. Built with FastAPI, PostgreSQL, LWC-style vanilla JS, and Kubernetes.

---

## 🌎 Live Demo

> **⚠️ This demo runs on HTTP (no TLS/HTTPS). Do not enter real credentials or personal information.**

| URL | What |
|-----|------|
| [testproveoportfolio.xyz/front-page/front-page.html](testproveoportfolio.xyz/front-page/front-page.html) | Frontend |
| [testproveoportfolio.xyz/docs](testproveoportfolio.xyz/docs) | API Docs (Swagger) |

**Before using the demo:**
- The demo uses the free tier of the Resend API, so you can create users, but verification emails will not be delivered. As a result, posting a company is restricted to admins or users authorized by an admin (currently, the creator is the only admin).
- Traffic is **unencrypted**, anyone on the network can see what you send and receive. Use throwaway credentials only (fake email, dummy password).
- The demo runs on a $21/mo DigitalOcean droplet (2GB RAM). Expect slower responses, especially on image uploads (NSFW detection runs on swap).
- For the best experience, use a **private/incognito browser window** so nothing gets cached or stored.
- If you want to be extra cautious, consider connecting from a **disposable VM** (VirtualBox, UTM, or a cloud instance you can delete afterward). Since there's no TLS, a throwaway environment ensures nothing persists on your machine: browser history, cookies, cached responses, DNS cache, all gone when you delete the VM.

---

## 🎯 Executive Summary

**What**: B2B marketplace connecting businesses with service providers  
**Stack**: FastAPI + PostgreSQL + Redis + MinIO + Kubernetes  
**Highlights**: 
- Database read/write splitting with streaming replication
- AI-powered NSFW detection (TensorFlow + OpenNSFW2)
- Kubernetes deployment with 7 pods across 7 services (2GB droplet configuration)
- Bilingual (ES/EN) with automatic translation fallback
- Zero-downtime deployments - Rolling updates replace pods one at a time (new pod starts → passes health checks → old pod terminates), ensuring traffic is always served

**Pod Breakdown (2GB Droplet):**
1. `postgres-primary-0` - StatefulSet from `04-postgres-primary.yaml`
2. `postgres-replica-0` - StatefulSet from `05-postgres-replica.yaml`
3. `redis-*` - Deployment from `06-redis.yaml`
4. `minio-*` - Deployment from `07-minio.yaml`
5. `image-service-*` - Deployment from `08-image-service.yaml` (1 replica)
6. `backend-*` - Deployment from `09-backend.yaml` (1 replica)
7. `nginx-*` - Deployment from `10-nginx.yaml`

---

## 🚀 Quick Start

### Docker Compose (Recommended for Local Demo)

```bash
# 1. Clone repository at stable commit
git clone https://github.com/uwuolguin/portfolio-2025.git
cd proveo
git checkout 4d5cadd4348797a3d9ee48f6ab2fd3cf08b4794b

# 2. Start all services (wait for image-service to finish loading)
docker compose up --build

# Wait until you see image-service logs showing "healthy" or repeated output
# Then in a new terminal:

# 3. Initialize database and seed data
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.database.manage_search_refresh_cron
docker compose exec backend python -m scripts.database.seed_test_data

# 4. Verify with tests (optional)
docker compose exec backend pytest app/tests/ -v

# 5. Access application
# Frontend: http://localhost/front-page/front-page.html
# API Docs: http://localhost/docs
```

### Kubernetes (Production Deployment)

See **[Kubernetes Deployment Guide](./k8s%20scripts/README.md)** for full k3s setup with PostgreSQL replication, load balancing, and production configuration.

---

## ✨ Key Technical Achievements

### 🗃️ **Architecture & Infrastructure**
- **Kubernetes (k3s) deployment** - 7 pods, 2 CPU cores, 2GB RAM (+2GB swap), 60GB storage
- **PostgreSQL streaming replication** - Primary for writes, replica for reads with automatic failback
- **Microservices** - Separate image processing service with NSFW detection
- **Zero-downtime deployments** - Rolling updates with health checks

### 💾 **Database Engineering**
- **Read/write splitting** - Automatic routing based on query type
- **Connection pooling** - 2-8 connections per pool (reduced for 2GB droplet) with health monitoring
- **Advanced search** - Materialized views + trigram similarity + full-text search
- **Auto-refresh** - pg_cron scheduled jobs for real-time search updates
- **Soft deletes** - Audit trail with cascading cleanup

### 🔒 **Security & Reliability**
- **JWT + CSRF protection** - HTTP-only cookies, constant-time comparison
- **RBAC** - Role-based access with email verification flow
- **Rate limiting** - Redis-backed per-IP and global limits
- **Retry logic** - Exponential backoff for transient failures
- **PostgreSQL SSL** - Self-signed certificates auto-generated by initContainers

### ⚡ **Performance Optimizations**
- **Redis caching** - 3-day TTL (64MB maxmemory, LRU eviction on droplet)
- **Image optimization** - JPEG 90% quality, PNG compression level 6
- **Async I/O** - asyncpg + uvicorn for high concurrency
- **Streaming uploads** - Memory-efficient file handling
- **CDN-ready** - Proper cache headers (30-day expiry)

### 🤖 **AI/ML Integration**
- **NSFW detection** - OpenNSFW2 model (TensorFlow 2.15)
- **Image validation** - Format, size, dimension checks
- **Automatic translation** - Google Translate API with fallback
- **Content moderation** - AI-powered blocking on model failure (fail-closed)

---

## 🛠️ Tech Stack

### Backend
- **FastAPI 0.120** - Modern async Python framework
- **asyncpg 0.30** - High-performance PostgreSQL driver
- **Pydantic v2** - Type-safe validation
- **Alembic** - Schema migrations
- **structlog** - Structured JSON logging

### Infrastructure
- **PostgreSQL 16** - Primary/replica replication, pg_cron, pg_trgm
- **Redis 7** - Cache + rate limiting
- **MinIO** - S3-compatible object storage
- **Kubernetes (k3s)** - Container orchestration
- **Nginx** - Reverse proxy + static file serving

### AI/ML
- **TensorFlow 2.15** - Neural network inference
- **OpenNSFW2** - NSFW content detection
- **Pillow** - Image processing
- **OpenCV** - Advanced image operations

### Frontend
- **Vanilla JavaScript (ES6+)** - No framework dependencies
- **Component architecture** - Modular, reusable patterns
- **LocalStorage** - Client-side state
- **Responsive CSS** - Mobile-first design

---

## 📚 Key Features

### User Management
- Email verification flow (Resend API)
- JWT authentication with CSRF protection
- Role-based access control (Admin/User)
- Account self-deletion with cascade cleanup

### Company Management
- One company per user (business rule enforcement)
- Bilingual support (Spanish/English)
- Image uploads with NSFW detection
- Full CRUD with ownership validation
- Admin management panel

### Search & Discovery
- Hybrid search (PostgreSQL full-text + trigram similarity)
- Multi-filter (keywords, location, category)
- Auto-refreshing materialized views (pg_cron)
- Pagination support

### DevOps
- Docker Compose for local development
- Kubernetes (k3s) for production
- Automated migrations (Alembic)
- Background jobs (APScheduler)
- Structured logging with correlation IDs
- Health checks with pool statistics

---

## 📁 Project Structure

```
proveo/
├── backend/                      # FastAPI application
│   ├── app/
│   │   ├── database/            # Read/write pools, transactions
│   │   ├── routers/             # API endpoints
│   │   ├── auth/                # JWT + CSRF
│   │   ├── services/            # Image processing, email
│   │   ├── schemas/             # Pydantic models
│   │   ├── middleware/          # CORS, logging, security
│   │   ├── redis/               # Cache, rate limiting
│   │   ├── templates/           # Email HTML templates
│   │   ├── utils/               # Validators, exceptions
│   │   └── tests/               # Pytest test suite
│   ├── alembic/                 # Database migrations
│   └── scripts/                 # Admin tools, seeding, maintenance
│
├── image-service/               # NSFW detection microservice
│   ├── main.py                  # FastAPI + TensorFlow
│   ├── image_validator.py       # Image processing logic
│   └── config.py                # Service configuration
│
├── k8s/                         # Kubernetes manifests
│   ├── 00-namespace.yaml
│   ├── 01-configmap.yaml
│   ├── 02-secrets.yaml
│   ├── 03-pvcs.yaml
│   ├── 04-postgres-primary.yaml
│   ├── 05-postgres-replica.yaml
│   ├── 06-redis.yaml
│   ├── 07-minio.yaml
│   ├── 08-image-service.yaml    # 1 replica (2GB droplet)
│   ├── 09-backend.yaml          # 1 replica (2GB droplet)
│   └── 10-nginx.yaml
│
├── k8s scripts/                 # Deployment automation
│   ├── 00-install-k3s.sh
│   ├── build-and-import-k3s.sh
│   ├── deploy-k3s-local.sh
│   ├── set-resend-key.sh
│   ├── cleanup.sh
│   ├── README.md                # K8s deployment guide
│
├── nginx/                       # Reverse proxy + frontend
│   ├── nginx.conf
│   ├── Dockerfile
│   └── frontend/                # Static files
│
├── postgres/                    # Custom PostgreSQL image
│   ├── Dockerfile
│   ├── init-db.sh
│   ├── init-ssl.sh
│   └── init-pgpass.sh
│
├── docker-compose.yml           # Local development
├── .env.example                 # Environment template
└── README.md                    # This file
```

---

## 🎓 Learning Highlights

This project demonstrates:

1. **Database Engineering** - Streaming replication, read/write splitting, connection pooling
2. **Microservices** - Service separation, load balancing, health checks
3. **Kubernetes** - StatefulSets, Deployments, Services, PVCs, ConfigMaps, Secrets, InitContainers
4. **Security** - JWT, CSRF, RBAC, SSL/TLS (self-signed certs auto-generated), rate limiting
5. **Performance** - Caching, async I/O, materialized views, image optimization
6. **DevOps** - Docker, K8s, migrations, background jobs, structured logging
7. **AI/ML** - TensorFlow model inference, NSFW detection
8. **Testing** - Pytest, rollback tests, integration tests
9. **Resource Constraints** - Running production-like workloads on minimal hardware with swap

---

## 🤝 Contact

**Andrés Olguín**  
Email: acos2014600836@gmail.com  
LinkedIn: https://www.linkedin.com/in/uwuolguin/  
GitHub: https://github.com/uwuolguin/

---

## 📄 License

Portfolio demonstration project - 2026
