# 🚀 Proveo - B2B Provider Marketplace Platform

**Overview**: A production-grade full-stack marketplace platform demonstrating modern cloud-native architecture, database replication, microservices, and scalable deployment patterns. Built with FastAPI, PostgreSQL, LWC-style vanilla JS, and Kubernetes.

---

## 🌎 Live Demo

| URL | What |
|-----|------|
| [https://testproveoportfolio.xyz/front-page/front-page.html](https://testproveoportfolio.xyz/front-page/front-page.html) | Frontend |

**Before using the demo:**
- The demo uses the free tier of the Resend API, so you can create users, but verification emails will not be delivered. As a result, posting a company is restricted to admins or users authorized by an admin (currently, the creator is the only admin).
- The demo runs on a $28/mo DigitalOcean droplet (4GB RAM, 2 AMD vCPUs, 60GB SSD, SFO3). Expect slower responses on image uploads — NSFW detection (399Mi actual) runs a TensorFlow model on every upload.
- For the best experience, use a **private/incognito browser window** so nothing gets cached or stored.

---

## 🎯 Executive Summary

**What**: B2B marketplace connecting businesses with service providers  
**Stack**: FastAPI + PostgreSQL + Redis + MinIO + Redpanda + Temporal + Kubernetes  
**Highlights**:
- Database read/write splitting with streaming replication
- AI-powered NSFW detection (TensorFlow + OpenNSFW2)
- Kubernetes deployment with 12 pods across 11 services on a 4GB droplet
- Bilingual (ES/EN) with automatic translation fallback
- HTTPS with Let's Encrypt TLS, auto-renewing certificates
- Zero-downtime deployments via rolling updates
- Event streaming pipeline — login/logout events published to Redpanda, routed to Temporal workers by language partition
- Durable workflow execution — AuthEventWorkflow fires a child SendNotificationWorkflow with fire-and-forget semantics

**Pod Breakdown (4GB Droplet):**
1. `postgres-primary-0` - StatefulSet from `04-postgres-primary.yaml`
2. `postgres-replica-0` - StatefulSet from `05-postgres-replica.yaml`
3. `redis-*` - Deployment from `06-redis.yaml`
4. `minio-*` - Deployment from `07-minio.yaml`
5. `image-service-*` - Deployment from `08-image-service.yaml`
6. `backend-*` - Deployment from `09-backend.yaml`
7. `nginx-*` - Deployment from `10-nginx.yaml`
8. `redpanda-0` - StatefulSet from `11-redpanda.yaml`
9. `consumer-*` - Deployment from `13-consumer.yaml`
10. `temporal-*` - Deployment from `14-temporal.yaml`
11. `temporal-ui-*` - Deployment from `14-temporal.yaml`
12. `temporal-worker-*` - Deployment from `15-temporal-worker.yaml`

---

## 🚀 Quick Start

### Docker Compose (Lightweight Local Preview)

The full production stack runs on Kubernetes, see the [Kubernetes Deployment Guide](./k8s%20scripts/README.md) for that. If you want a quick local look at the core app (no Kafka, no NSFW model, no k8s), use this earlier snapshot:

```bash
# 1. Clone repository
git clone https://github.com/uwuolguin/portfolio-2025.git
cd portfolio-2025

# 2. Switch to the lightweight local snapshot
git checkout 4d5cadd4348797a3d9ee48f6ab2fd3cf08b4794b

# 3. Start core services
docker compose up --build

# Wait until you see image-service logs showing "healthy" or repeated output
# Then in a new terminal:

# 4. Initialize database and seed data
docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.database.manage_search_refresh_cron
docker compose exec backend python -m scripts.database.seed_test_data

# 5. Verify with tests (optional)
docker compose exec backend pytest app/tests/ -v

# 6. Access application
# Frontend: http://localhost/front-page/front-page.html
# API Docs: http://localhost/docs
```

### Kubernetes (Production Deployment)

See **[Kubernetes Deployment Guide](./k8s%20scripts/README.md)** for full k3s setup with PostgreSQL replication, TLS termination, and production configuration.

> **HTTPS on the droplet:** If you want to deploy with HTTPS (required for secure cookies and production behaviour), you need to provision a TLS certificate before running the deploy script. See **[SSL Setup Guide](./SSL_SETUP.md)** for the full certbot + Let's Encrypt flow, it covers cert provisioning, making certs accessible to the deploy user, the nginx config changes, and auto-renewal via cron. Run that guide first on a clean droplet, then come back to **[Kubernetes Deployment Guide](./k8s%20scripts/README.md)**.

---

## ✨ Key Technical Achievements

### 🗃️ **Architecture & Infrastructure**
- **Kubernetes (k3s) deployment** - 12 pods, 2 AMD vCPUs, 4GB RAM (+2GB swap), 60GB SSD, SFO3
- **PostgreSQL streaming replication** - Primary for writes, replica for reads with automatic failback
- **Microservices** - Separate image processing service with NSFW detection
- **Zero-downtime deployments** - Rolling updates with health checks
- **TLS termination at nginx edge** - Let's Encrypt certificates, auto-renewed via cron, injected into cluster as Kubernetes secrets

### 💾 **Database Engineering**
- **Read/write splitting** - Automatic routing based on query type
- **Connection pooling** - asyncpg pool with health monitoring
- **Advanced search** - Materialized views + trigram similarity + full-text search
- **Auto-refresh** - pg_cron scheduled jobs for real-time search updates
- **Soft deletes** - Audit trail with cascading cleanup

### 🔒 **Security & Reliability**
- **HTTPS enforced** - TLS 1.2/1.3 only, HSTS with 1-year max-age, preload
- **JWT + CSRF protection** - HTTP-only cookies, constant-time comparison
- **Secure cookies** - `Secure` flag enforced in production, HTTPS-only transmission
- **RBAC** - Role-based access with email verification flow
- **Rate limiting** - Redis-backed per-IP and global limits
- **Security headers** - CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- **Retry logic** - Exponential backoff for transient failures
- **PostgreSQL SSL** - Self-signed certificates auto-generated by initContainers
- **Mixed auth policy** - Encryption enforced at the application layer per service; backend uses `sslmode=require`, Temporal connects without SSL by design — all traffic is internal cluster network only

### ⚡ **Performance Optimizations**
- **Redis caching** - 3-day TTL (64MB maxmemory, LRU eviction)
- **Image optimization** - JPEG 90% quality, PNG compression level 6
- **Async I/O** - asyncpg + uvicorn for high concurrency
- **Streaming uploads** - Memory-efficient file handling
- **CDN-ready** - Proper cache headers (30-day expiry)
- **HTTP/2** - Enabled at nginx for all HTTPS connections

### 🤖 **AI/ML Integration**
- **NSFW detection** - OpenNSFW2 model (TensorFlow 2.15), 399Mi actual memory footprint
- **Image validation** - Format, size, dimension checks
- **Automatic translation** - Google Translate API with fallback
- **Content moderation** - AI-powered blocking on model failure (fail-closed)

### 📨 **Event Streaming Pipeline**
- **Redpanda (Kafka-compatible)** - Login and logout events published as JSON to durable topics with 24h retention
- **Explicit partition routing** - `PARTITION_MAP = {"es": 0, "en": 1}` partition assignment is deterministic and self-documenting
- **Fire-and-forget publishing** - Auth endpoints never block on Kafka; publish failures are logged and swallowed
- **Self-healing producer** - `asyncio.Lock` prevents concurrent reconnect races; lazy reconnect recovers automatically if Redpanda was down at startup
- **Graceful degradation** - Redpanda outage has zero user-visible impact; auth continues normally
- **Init Job pattern** - Topics created by a one-shot Kubernetes Job after the StatefulSet is confirmed healthy

### ⏱️ **Durable Workflow Execution (Temporal)**
- **AuthEventWorkflow** - Parent workflow: runs log_event_activity, then fires SendNotificationWorkflow as a child with fire-and-forget semantics
- **SendNotificationWorkflow** - Child workflow: runs independently after parent completes, executes send_mock_email_activity
- **ABANDON parent close policy** - Child workflow continues even if the parent pod crashes or completes
- **Deterministic workflow IDs** - `auth-{topic}-{partition}-{offset}` — duplicate Kafka delivery is rejected by Temporal, never executed twice
- **Ringpop membership** - Pod IP advertised via Kubernetes downward API so the internal service mesh routes correctly even when scaled to multiple replicas

---

## 🛠️ Tech Stack

### Backend
- **FastAPI 0.120** - Modern async Python framework
- **asyncpg 0.30** - High-performance PostgreSQL driver
- **aiokafka** - Async Kafka producer for Redpanda event publishing
- **temporalio 1.7** - Durable workflow execution SDK
- **Pydantic v2** - Type-safe validation
- **Alembic** - Schema migrations
- **structlog** - Structured JSON logging

### Infrastructure
- **PostgreSQL 16** - Primary/replica replication, pg_cron, pg_trgm
- **Redis 7** - Cache + rate limiting
- **MinIO** - S3-compatible object storage
- **Redpanda v24.2** - Kafka-compatible event broker (StatefulSet, persistent storage)
- **Temporal 1.24** - Durable workflow execution server (PostgreSQL persistence)
- **Kubernetes (k3s)** - Container orchestration
- **Nginx** - Reverse proxy + TLS termination + static file serving
- **Let's Encrypt** - Automated TLS certificates via certbot

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
│   │   ├── kafka/               # Redpanda producer + consumer worker
│   │   ├── temporal/            # Workflows, activities, worker
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
│   ├── 08-image-service.yaml
│   ├── 09-backend.yaml
│   ├── 10-nginx.yaml            # TLS termination + HTTP→HTTPS redirect
│   ├── 11-redpanda.yaml         # Kafka-compatible broker (StatefulSet)
│   ├── 12-redpanda-init.yaml    # One-shot Job, creates topics after broker ready
│   ├── 13-consumer.yaml         # Redpanda consumer, routes events to Temporal
│   ├── 14-temporal.yaml         # Temporal server + UI
│   └── 15-temporal-worker.yaml  # Temporal worker (AuthEventWorkflow)
│
├── k8s scripts/                 # Deployment automation
│   ├── 00-install-k3s.sh
│   ├── build-and-import-k3s.sh
│   ├── deploy-k3s-local.sh
│   ├── set-resend-key.sh
│   ├── cleanup.sh
│   └── README.md                # K8s deployment guide
│
├── nginx/                       # Reverse proxy + frontend
│   ├── nginx.conf               # Local dev config (Docker Compose)
│   ├── Dockerfile
│   └── frontend/                # Static files
│
├── postgres/                    # Custom PostgreSQL image
│   ├── Dockerfile
│   ├── init-db.sh               # Creates portfolio, temporal, temporal_visibility
│   ├── init-ssl.sh              # SSL bootstrap + pg_hba config
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
2. **Event Streaming** - Redpanda/Kafka producer, explicit partition routing, graceful degradation, Kubernetes Job ordering for broker initialization
3. **Durable Workflows** - Temporal child workflows, fire-and-forget with ABANDON policy, deterministic workflow IDs for at-least-once deduplication
4. **Microservices** - Service separation, load balancing, health checks
5. **Kubernetes** - StatefulSets, Deployments, Jobs, Services, PVCs, ConfigMaps, Secrets, InitContainers, downward API
6. **Security** - HTTPS/TLS, JWT, CSRF, RBAC, secure cookies, HSTS, CSP, rate limiting, per-service SSL policy
7. **Performance** - Caching, async I/O, materialized views, image optimization, HTTP/2
8. **DevOps** - Docker, K8s, certbot, auto-renewal cron, migrations, structured logging
9. **AI/ML** - TensorFlow model inference, NSFW detection
10. **Testing** - Pytest, rollback tests, integration tests
11. **Resource Constraints** - Running 12 production-grade pods on a 4GB droplet; actual pod footprint ~1.1GB leaving headroom for Grafana/Prometheus

---

## 🤝 Contact

**Andrés Olguín**  
Email: acos2014600836@gmail.com  
LinkedIn: https://www.linkedin.com/in/uwuolguin/  
GitHub: https://github.com/uwuolguin/

---

## 📄 License

Portfolio demonstration project - 2026