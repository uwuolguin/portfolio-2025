# Proveo: B2B Provider Marketplace

A full-stack marketplace platform consolidating five years of professional experience into a single deployable project. Every component in this stack reflects tools used in production at some point in my career: PostgreSQL replication, Kafka event streaming, Temporal workflows, Kubernetes, NSFW content moderation, and observability.

The domain is a B2B marketplace where companies list their services. Simple enough to build as a side project, with enough operational surface area to make the infrastructure decisions meaningful.

Runs on a single DigitalOcean droplet (4GB RAM, 2 AMD vCPUs, 60GB SSD). No dev/staging split, one environment, manual deploys — except for commits prefixed with `prod-`, which trigger a GitHub Actions pipeline that runs the deployment scripts automatically.

---

## 🌎 Live Demo

| URL | What |
|-----|------|
| [https://testproveoportfolio.xyz/front-page/front-page.html](https://testproveoportfolio.xyz/front-page/front-page.html) | Frontend |
| `https://testproveoportfolio.xyz/grafana` | Grafana: live pipeline logs |

**A few things to know before poking around:**
- Email verification uses Resend free tier — delivery is not guaranteed. Company creation is restricted to admin-verified users for now, but you can sign up still
- Private/incognito window recommended

---

## 🏗️ Architecture

```
Browser → nginx (TLS) → FastAPI backend → PostgreSQL primary (writes)
                                        → PostgreSQL replica (reads)
                                        → Redis (cache + rate limiting)
                                        → MinIO (image storage)
                                        → LibreTranslate (translation)
                                        → Image Service (NSFW detection)

Login/Logout → Redpanda → Consumer → Temporal → AuthEventWorkflow
                                              → SendNotificationWorkflow
                                                (child, fire-and-forget)

temporal-worker → Promtail → Loki → Grafana
```

---

## 🛠️ Stack

### Backend
- **FastAPI 0.120** + **asyncpg 0.30** — async Python, raw SQL, no ORM
- **Pydantic v2** — validation
- **Alembic** — migrations
- **structlog** — structured JSON logging throughout, including Temporal SDK internals and Rust core logs via `LogForwardingConfig`
- **aiokafka** — Redpanda producer + consumer worker
- **temporalio 1.7** — workflow SDK

### Frontend
- **Vanilla ES6+** — no framework, no build pipeline
- **DOMPurify 3.0.8** — XSS sanitization wired in, currently dormant (all DOM writes go through `textContent`)
- **ES modules** — native browser imports, component-per-file

### Infrastructure
- **PostgreSQL 16** — primary/replica streaming replication, pg_cron, pg_trgm, materialized views
- **Redis 7** — caching (3-day TTL, LRU eviction, 64MB limit)
- **MinIO** — S3-compatible object storage, self-hosted
- **LibreTranslate** — self-hosted translation, ES↔EN only (`LT_LOAD_ONLY=en,es`)
- **Redpanda v24.2** — Kafka-compatible broker, StatefulSet, persistent storage
- **Temporal 1.24** — durable workflow execution, PostgreSQL persistence
- **k3s** — single-node Kubernetes
- **Nginx** — TLS termination, HTTP→HTTPS redirect, HTTP/2, gzip, rate limiting, security headers
- **Let's Encrypt** — automated TLS via certbot, auto-renewed via cron

### Observability
- **Grafana** — live dashboard, publicly accessible with rotating demo credentials
- **Loki** — log aggregation
- **Promtail** — scrapes `temporal-worker` pod logs only, routes to Loki

### AI/ML
- **TensorFlow 2.15** + **OpenNSFW2** — NSFW content detection on upload
- **Pillow** — image validation and optimization

---

## 🔍 How Things Work

### PostgreSQL Replication
Write pool connects to `postgres-primary`, read pool connects to `postgres-replica`. On startup the app calls `pg_is_in_recovery()` to verify the replica is actually in standby mode and falls back to primary for reads if it isn't.

### Search
Materialized view (`proveo.company_search`) with a GIN trigram index. Short queries (`< 4 chars`) use `ILIKE`, longer ones use `similarity()` scoring. pg_cron refreshes the view every minute with `REFRESH MATERIALIZED VIEW CONCURRENTLY` so reads are never blocked.

### Image Service
Separate microservice with its own Dockerfile and deployment. Validates format, dimensions, and NSFW score before writing to MinIO. Circuit breaker pattern prevents cascade failures if the service is unavailable. Images stream directly — no full file buffering in the backend.

### Kafka + Temporal Pipeline
Login and logout events publish to Redpanda, partitioned by language (`es → 0`, `en → 1`). A consumer worker routes them to Temporal's `AuthEventWorkflow`, which logs the event and fires a child `SendNotificationWorkflow` with ABANDON policy: the child keeps running after the parent completes.

The workload running through it is simple (structured log + mock email) but the wiring is real: explicit partition routing, manual offset commits for at-least-once delivery, deterministic workflow IDs so duplicate Kafka delivery doesn't execute the workflow twice, fire-and-forget child workflows. Swap the mock email activity for a real one and the pipeline is production-ready.

### Live Pipeline Verification: Grafana
Go to `https://testproveoportfolio.xyz/grafana` and log in with the demo credentials — username is always `demo`, today's password is in [this gist](https://gist.github.com/uwuolguin/REPLACE_WITH_GIST_ID). Then create an account on the demo site and log in. The event shows up in the dashboard within seconds.

What you'll see:
- The JSON log line with `user_uuid`, `email`, `lang`, `event_type`, `partition`, `offset`
- `auth_event_received`: parent workflow ran
- `mock_email_sent`: child workflow ran independently after parent completed
- Partition routing: es on 0, en on 1

Full chain: login endpoint → `asyncio.create_task(kafka_producer.publish_event(...))` → Redpanda → consumer offset commit → Temporal `AuthEventWorkflow` → `log_event_activity` → child `SendNotificationWorkflow` → `send_mock_email_activity` → structlog JSON → Promtail scrapes `temporal-worker` → Loki → Grafana.

### TLS
Certbot provisions Let's Encrypt certs on the droplet, they get copied to `/home/deploy/certs/` and loaded into Kubernetes as a `tls-secret`. Nginx terminates TLS, sets `X-Forwarded-Proto: https`. Root cron job handles renewal: updates the secret and restarts nginx.

### Structured Logging
Every caught exception across every service is JSON via structlog. In the `temporal-worker` pod specifically, uncaught exceptions are also captured as JSON: asyncio loop exceptions via `install_async_exception_handler` and synchronous crashes via `sys.excepthook`. Temporal SDK Python-side logs and Rust core logs are routed through `LogForwardingConfig` and formatted as JSON in that same pod. Gaps: threads, multiprocessing, and OS-level errors that occur before the asyncio worker starts (such as missing env vars resolved at import time) are not guaranteed to be JSON. The `temporal-worker` pod logs are scraped by Promtail and indexed in Loki: queryable live in Grafana.

### Frontend
Vanilla ES6+, no framework, no build step. Components rebuild on state change by clearing and reconstructing the DOM — straightforward and fast for this scale. The known roughness is the language toggle refetching bilingual data that's already in memory; the data model already has both `name_es` and `name_en` in every response so the fix is trivial, marked for refactoring.

---

## ⚠️ Known Gaps

- One environment. No dev/staging split.
- CI/CD is scoped to `prod-*` commit prefixes via GitHub Actions: not a full pipeline.
- No backups. Local-path PVCs on one node: if the droplet dies, data goes with it.
- `force_rollback` on DB methods is a testing convenience, not a production pattern.
- Frontend language toggle refetches data already in memory: marked for refactoring.

---

## 📦 Pod Breakdown (4GB Droplet)

| Pod | Manifest | Actual RAM |
|-----|----------|-----------|
| `postgres-primary-0` | `04-postgres-primary.yaml` | ~107Mi |
| `postgres-replica-0` | `05-postgres-replica.yaml` | ~35Mi |
| `redis-*` | `06-redis.yaml` | ~5Mi |
| `minio-*` | `07-minio.yaml` | ~91Mi |
| `image-service-*` | `08-image-service.yaml` | ~399Mi |
| `backend-*` | `09-backend.yaml` | ~69Mi |
| `nginx-*` | `10-nginx.yaml` | ~7Mi |
| `redpanda-0` | `11-redpanda.yaml` | ~197Mi |
| `consumer-*` | `13-consumer.yaml` | ~28Mi |
| `temporal-*` | `14-temporal.yaml` | ~149Mi |
| `temporal-ui-*` | `14-temporal.yaml` | ~3Mi |
| `temporal-worker-*` | `15-temporal-worker.yaml` | ~50Mi |
| `libretranslate-*` | `16-libretranslate.yaml` | ~300Mi |
| `loki-*` | `17-monitoring.yaml` | ~128Mi |
| `promtail-*` | `17-monitoring.yaml` | ~64Mi |
| `grafana-*` | `17-monitoring.yaml` | ~128Mi |

---

## 🚀 Quick Local Preview

The full production stack runs on Kubernetes — see the [Kubernetes Deployment Guide](./k8s%20scripts/README.md) for that. If you want a quick local look at the core app (no Kafka, no NSFW model, no k8s), use this earlier snapshot:

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

### Kubernetes (Full Stack)

See **[Kubernetes Deployment Guide](./k8s%20scripts/README.md)**.
For HTTPS first: **[SSL Setup Guide](./SSL_SETUP.md)**.

---

## 📁 Project Structure

```
proveo/
├── .github/
│   └── workflows/
│       └── deploy.yml           # Triggers on prod-* commits, SSHs into droplet and runs deploy scripts
│
├── backend/                      # FastAPI application
│   ├── app/
│   │   ├── database/            # Read/write pools, transactions
│   │   ├── routers/             # API endpoints
│   │   ├── auth/                # JWT + CSRF
│   │   ├── services/            # Image processing, email, translation, circuit breaker
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
│   ├── 15-temporal-worker.yaml  # Temporal worker (AuthEventWorkflow)
│   ├── 16-libretranslate.yaml   # Self-hosted translation service (ES↔EN)
│   └── 17-monitoring.yaml       # Grafana + Loki + Promtail (temporal-worker logs only)
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
└── README.md
```

---

## Contact

**Andrés Olguín**

Email: acos2014600836@gmail.com
LinkedIn: https://www.linkedin.com/in/uwuolguin/
GitHub: https://github.com/uwuolguin/