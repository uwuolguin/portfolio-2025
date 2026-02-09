# 🚀 Proveo - B2B Provider Marketplace Platform

**Overview**: A production-grade full-stack marketplace platform demonstrating modern cloud-native architecture, database replication, microservices, and scalable deployment patterns. Built with FastAPI, PostgreSQL, LWC-style vanilla JS, and Kubernetes.

---

## 🌐 Live Demo

> **⚠️ This demo runs on HTTP (no TLS/HTTPS). Do not enter real credentials or personal information.**

**Live at**: [http://YOUR_DROPLET_IP](http://YOUR_DROPLET_IP)

| URL | What |
|-----|------|
| [http://YOUR_DROPLET_IP/front-page/front-page.html](http://YOUR_DROPLET_IP/front-page/front-page.html) | Frontend |
| [http://YOUR_DROPLET_IP/docs](http://YOUR_DROPLET_IP/docs) | API Docs (Swagger) |
| [http://YOUR_DROPLET_IP/redoc](http://YOUR_DROPLET_IP/redoc) | API Docs (ReDoc) |

**Before using the demo:**
- Traffic is **unencrypted** — anyone on the network can see what you send and receive. Use throwaway credentials only (fake email, dummy password).
- The demo runs on a $21/mo DigitalOcean droplet (2GB RAM). Expect slower responses, especially on image uploads (NSFW detection runs on swap).
- For the best experience, use a **private/incognito browser window** so nothing gets cached or stored.
- If you want to be extra cautious, consider connecting from a **disposable VM** (VirtualBox, UTM, or a cloud instance you can delete afterward). Since there's no TLS, a throwaway environment ensures nothing persists on your machine — browser history, cookies, cached responses, DNS cache — all gone when you delete the VM.

---

## 🎯 Executive Summary

**What**: B2B marketplace connecting businesses with service providers  
**Stack**: FastAPI + PostgreSQL + Redis + MinIO + Kubernetes  
**Highlights**: 
- Database read/write splitting with streaming replication
- AI-powered NSFW detection (TensorFlow + OpenNSFW2)
- Kubernetes deployment with 9 pods across 6 services
- Bilingual (ES/EN) with automatic translation fallback
- Zero-downtime deployments with rolling updates

---

## 🚀 Quick Start

### Docker Compose (Recommended for Demo)

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

For deploying to a **DigitalOcean droplet**, see **[DigitalOcean Deployment Guide](./k8s%20scripts/README_DIGITAL_OCEAN.md)** — optimized manifests and scripts for a 2GB RAM droplet with all features enabled.

---

## ✨ Key Technical Achievements

### 🏗️ **Architecture & Infrastructure**
- **Kubernetes (k3s) deployment** - 9 pods, 4 CPU cores, 8GB RAM, 50GB storage
- **PostgreSQL streaming replication** - Primary for writes, replica for reads with automatic failback
- **Microservices** - Separate image processing service with NSFW detection
- **Load balancing** - 2x backend, 2x image service replicas
- **Zero-downtime deployments** - Rolling updates with health checks

### 💾 **Database Engineering**
- **Read/write splitting** - Automatic routing based on query type
- **Connection pooling** - 5-20 connections per pool with health monitoring
- **Advanced search** - Materialized views + trigram similarity + full-text search
- **Auto-refresh** - pg_cron scheduled jobs for real-time search updates
- **Soft deletes** - Audit trail with cascading cleanup

### 🔒 **Security & Reliability**
- **JWT + CSRF protection** - HTTP-only cookies, constant-time comparison
- **RBAC** - Role-based access with email verification flow
- **Rate limiting** - Redis-backed per-IP and global limits
- **Retry logic** - Exponential backoff for transient failures
- **PostgreSQL SSL** - Encrypted connections with self-signed certificates

### ⚡ **Performance Optimizations**
- **Redis caching** - 3-day TTL with graceful degradation
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
│   ├── 08-image-service.yaml    # 2 replicas
│   ├── 09-backend.yaml          # 2 replicas
│   └── 10-nginx.yaml
│
├── k8s scripts/                 # Deployment automation
│   ├── 00-install-k3s.sh
│   ├── build-and-import-k3s.sh
│   ├── deploy-k3s-local.sh
│   ├── cleanup.sh
│   ├── README.md                # K8s deployment guide
│   └── README_DIGITAL_OCEAN.md  # DigitalOcean droplet guide
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

## 📖 Documentation

- **[Kubernetes Deployment Guide](./k8s%20scripts/README.md)** - Full k8s setup, scaling, monitoring
- **[DigitalOcean Droplet Guide](./k8s%20scripts/README_DIGITAL_OCEAN.md)** - 2GB droplet deployment with optimized manifests
- **API Docs (Swagger)**: http://localhost/docs
- **API Docs (ReDoc)**: http://localhost/redoc

---

## 🎓 Learning Highlights

This project demonstrates:

1. **Database Engineering** - Streaming replication, read/write splitting, connection pooling
2. **Microservices** - Service separation, load balancing, health checks
3. **Kubernetes** - StatefulSets, Deployments, Services, PVCs, ConfigMaps, Secrets
4. **Security** - JWT, CSRF, RBAC, SSL/TLS, rate limiting
5. **Performance** - Caching, async I/O, materialized views, image optimization
6. **DevOps** - Docker, K8s, migrations, background jobs, structured logging
7. **AI/ML** - TensorFlow model inference, NSFW detection
8. **Testing** - Pytest, rollback tests, integration tests

---

## 🤝 Contact

**Andrés Olguín**  
Email: acos2014600836@gmail.com  
LinkedIn: https://www.linkedin.com/in/uwuolguin/  
GitHub: https://github.com/uwuolguin/

---

## 📄 License

Portfolio demonstration project - 2026

---

> ⚠️ **SECURITY WARNING - READ BEFORE PRODUCTION DEPLOYMENT**
>
> This codebase contains a **development-only admin CSRF bypass mechanism** in `backend/app/auth/csrf.py` that **MUST be removed** before any production deployment. Remove the entire admin bypass block, all `ADMIN_BYPASS_IPS` references, and `/use-postman-or-similar-to-bypass-csrf` endpoints. This bypass exists solely for testing purposes and represents a critical security vulnerability if deployed to production.