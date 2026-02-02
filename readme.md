# 🚀 Proveo - B2B Provider Marketplace Platform

**Overview**: A production-grade full-stack marketplace platform demonstrating modern cloud-native architecture, database replication, microservices, and scalable deployment patterns. Built with FastAPI, PostgreSQL, LWC-style vanilla JS, and Kubernetes.

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
- **NSFW detection** - AI/ML-powered content moderation (blocks uploads on model failure)

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

🚀 Quick Start

Docker Compose (Recommended for Demo)
bash# 1. Clone repository at stable commit
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
# Frontend: http://localhost
# API Docs: http://localhost/docs


Kubernetes (Production Deployment)
See Kubernetes Deployment Guide for full k3s setup, manifests, and production configuration.

## 🏗️ Architecture

### High-Level Overview
```
Internet → Load Balancer (nginx)
              ↓
      ┌───────┴──────────┐
      ↓                  ↓
   Backend (2x)    Image Service (2x)
      ↓                  ↓
   ┌──┴──────┬──────────┴──┬────────┐
   ↓         ↓             ↓        ↓
PostgreSQL  Redis        MinIO    pg_cron
Primary/Replica
```

### Database Read/Write Splitting
```python
# Automatic routing based on operation type
from app.database.connection import get_db_read, get_db_write

# READ operations → Replica (fallback to Primary)
@router.get("/items")
async def list_items(db = Depends(get_db_read)):
    return await DB.get_all_items(conn=db)

# WRITE operations → Primary only
@router.post("/items")
async def create_item(db = Depends(get_db_write)):
    return await DB.create_item(conn=db, ...)
```

### Kubernetes Resource Distribution
| Service | Replicas | CPU | Memory | Storage |
|---------|----------|-----|--------|---------|
| Nginx | 1 | 100m | 128Mi | - |
| Backend | 2 | 250m | 512Mi | - |
| Image Service | 2 | 500m | 1Gi | - |
| PostgreSQL Primary | 1 | 500m | 512Mi | 10Gi |
| PostgreSQL Replica | 1 | 250m | 512Mi | 10Gi |
| Redis | 1 | 100m | 128Mi | 1Gi |
| MinIO | 1 | 250m | 256Mi | 20Gi |
| **Total** | **9 pods** | **2.2 cores** | **4.5GB** | **41GB** |

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
├── backend/               # FastAPI application
│   ├── app/
│   │   ├── database/     # Read/write pools, transactions
│   │   ├── routers/      # API endpoints
│   │   ├── auth/         # JWT + CSRF
│   │   ├── services/     # Image processing, email
│   │   └── schemas/      # Pydantic models
│   ├── alembic/          # Database migrations
│   └── scripts/          # Admin tools, seeding
│
├── image-service/        # NSFW detection microservice
│   ├── main.py           # FastAPI + TensorFlow
│   └── image_validator.py
│
├── k8s/                  # Kubernetes manifests
│   ├── 04-postgres-primary.yaml
│   ├── 05-postgres-replica.yaml
│   ├── 08-image-service.yaml (2 replicas)
│   └── 09-backend.yaml (2 replicas)
│
├── nginx/                # Reverse proxy + frontend
├── postgres/             # Custom PostgreSQL image
└── docker-compose.yml    # Local development
```

---

## 🧪 Testing

```bash
# Run all tests
docker compose exec backend pytest app/tests/ -v

# Key test suites:
# - User authentication flow
# - Company CRUD operations
# - Database replication verification
# - Image upload with NSFW detection
# - Materialized view refresh
# - Orphan image cleanup
```

---

## 📖 Documentation

- **[Kubernetes Deployment Guide](./k8s%20scripts/README.md)** - Full k8s setup, scaling, monitoring
- **API Docs (Swagger)**: http://localhost/docs
- **API Docs (ReDoc)**: http://localhost/redoc
http://localhost/front-page/front-page.html
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
Email: your.email@example.com  
LinkedIn: [linkedin.com/in/yourprofile](#)  
GitHub: [github.com/yourusername](#)

---

## 📄 License

Portfolio demonstration project - 2026

---

> ⚠️ **SECURITY WARNING - READ BEFORE PRODUCTION DEPLOYMENT**
>
> This codebase contains a **development-only admin CSRF bypass mechanism** in `backend/app/auth/csrf.py` that **MUST be removed** before any production deployment. Remove the entire admin bypass block, all `ADMIN_BYPASS_IPS` references, and `/use-postman-or-similar-to-bypass-csrf` endpoints. This bypass exists solely for testing purposes and represents a critical security vulnerability if deployed to production.