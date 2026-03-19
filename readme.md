# Proveo: B2B Provider Marketplace

A full-stack marketplace platform consolidating five years of professional experience into a single deployable project. Every component in this stack reflects tools used in production at some point in my career: PostgreSQL replication, Kafka event streaming, Temporal workflows, Kubernetes, Automated Content Moderation (Computer Vision), and observability.

The domain is a B2B marketplace where companies list their services. Simple enough to build as a side project, with enough operational surface area to make the infrastructure decisions meaningful.

Runs on a single DigitalOcean droplet (4GB RAM, 2 AMD vCPUs, 60GB SSD). No dev/staging split, one environment, manual deploys, except for commits prefixed with `prod-`, which trigger a GitHub Actions pipeline that runs the deployment scripts automatically. The prefix-based trigger avoids burning GitHub Actions minutes on work-in-progress commits.

---

## 🌎 Live Demo

| URL | What |
|-----|------|
| [https://testproveoportfolio.xyz/front-page/front-page.html](https://testproveoportfolio.xyz/front-page/front-page.html) | Frontend |
| `https://testproveoportfolio.xyz/grafana` | Grafana: live pipeline logs |

**Try the live pipeline:** open Grafana first, then sign up and log in on the frontend — your login event will show up in the dashboard within seconds.

**Grafana demo credentials:**

> **Username:** `demo`
> **Password:** today's password is in [this gist](https://gist.github.com/uwuolguin/REPLACE_WITH_GIST_ID) (rotates daily)

**A few things to know before poking around:**
- Email verification uses the Resend free tier, so only the email acos2014600836@gmail.com can receive the verification link. Company creation is restricted to admin-verified users for now, but you can still sign up.
- Private/incognito window recommended. Use passwords that do not relate to the ones you normally use, even though passwords are hashed.

---

## 🏗️ Architecture

### 🧩 Services Overview

> Every service runs inside a single Kubernetes namespace (`portfolio`) on k3s, connected via ClusterIP — nothing reaches the internet except through nginx.

```
Browser
   │
   ▼
nginx  ──── TLS termination (Let's Encrypt) · HTTP→HTTPS redirect
            reverse proxy (backend + image-service) · rate limiting · security headers
   │
   ▼
FastAPI backend (uvicorn, 1 worker — pinned to minimize RAM footprint on 4GB node;
                 asyncpg handles I/O concurrency)
   │
   ├──▶  PostgreSQL primary   — writes, DDL, Alembic migrations (pg_cron, SSL, WAL streaming)
   │
   ├──▶  PostgreSQL replica   — reads only, hot standby, physical replication slot
   │
   ├──▶  Redis                — response cache (allkeys-LRU, 64 MB cap) + rate limiting
   │
   ├──▶  MinIO                — S3-compatible object storage for user-uploaded images
   │
   ├──▶  Image Service        — automated content moderation via TensorFlow before images land in MinIO
   │
   └──▶  LibreTranslate       — self-hosted offline translation (en ↔ es, no external API dependency)
```

| Service | Role | Notes |
|---|---|---|
| **nginx** | Reverse proxy + TLS edge | Only pod exposed via `LoadBalancer`; everything else is `ClusterIP` |
| **FastAPI backend** | REST API | Python, asyncpg connection pool, JWT auth, CSRF protection |
| **PostgreSQL primary** | Write database | pg_cron, scram-sha-256, SSL, WAL level `replica` |
| **PostgreSQL replica** | Read database | Streams WAL from primary via replication slot; `hot_standby = on` |
| **Redis** | Cache | TTL-based invalidation; LRU eviction under memory pressure |
| **MinIO** | Object storage | Bucket `images`; accessed internally — never exposed through nginx directly |
| **Image Service** | Content moderation | Intercepts uploads, runs TensorFlow model, rejects or stores in MinIO |
| **LibreTranslate** | Translation | `LT_LOAD_ONLY=en,es` keeps memory at ~300 MB; fully offline after model download |

---

### ⚡ End-to-End Event Flow — Auth Event Pipeline

> A user logs in or out → the event travels through four decoupled layers before producing a structured audit log and a (mock) notification email. Zero synchronous coupling between any of them.

```
User login / logout
      │
      ▼
FastAPI backend
  publishes event via asyncio.create_task (fire-and-forget for sub-millisecond
  API response times; for zero-loss critical events, await would be used instead)
  topic: user-logins  │  user-logouts
  partition key: lang (es → p0 · en → p1)
      │
      ▼
Redpanda  ──── single-broker StatefulSet, 2 partitions/topic, 24 h retention
               partitioned by lang to demonstrate deterministic routing and consumer
               locality; in high-scale production, user_uuid would distribute load evenly
      │
      ▼
Consumer (aiokafka)
  polls Redpanda, deserialises event, commits offset only after hand-off succeeds
  at-least-once delivery guarantee
      │
      ▼
Temporal server  ──── durable workflow engine backed by PostgreSQL
  receives: StartWorkflow(AuthEventWorkflow, payload)
      │
      ▼
Temporal worker (portfolio-backend image, different CMD)
  executes AuthEventWorkflow
      │
      ├──▶  log_event_activity
      │       structlog → JSON line → stdout
      │                                │
      │                                ▼
      │                         Promtail (DaemonSet)
      │                           tails /var/log/pods/…
      │                                │
      │                                ▼
      │                           Loki  ──── indexes JSON fields (level, event,
      │                                      workflow_id, event_type, lang)
      │                                │
      │                                ▼
      │                           Grafana  ──── LogQL queries, label filters,
      │                                         admin login, Loki pre-wired as
      │                                         default datasource
      │
      └──▶  send_mock_email_activity  (fire-and-forget child workflow)
              logs what WOULD be sent — swap for real Resend call in production
```

**Why each layer exists:**

- **Redpanda** decouples the HTTP request from all downstream processing — the API response returns instantly; the event pipeline runs asynchronously.
- **Consumer → Temporal hand-off** makes the workflow durable. If the Temporal server restarts mid-execution, the workflow resumes from the last checkpoint — no event is lost.
- **Temporal** provides retries, timeouts, and full execution history without any custom retry logic in application code.
- **Promtail → Loki → Grafana** gives observability into workflow execution without instrumenting the application beyond `structlog` JSON output.

---

## 🛠️ Stack

### Backend
- **FastAPI 0.120** + **asyncpg 0.30**: async Python, raw SQL, no ORM
- **Pydantic v2**: validation
- **Alembic**: migrations
- **structlog**: structured JSON logging throughout, including Temporal SDK internals and Rust core logs via `LogForwardingConfig`
- **aiokafka**: Redpanda producer + consumer worker
- **temporalio 1.7**: workflow SDK

### Frontend
- **Vanilla ES6+**: no framework, no build pipeline
- **DOMPurify 3.0.8**: XSS sanitization wired in, currently dormant (all DOM writes go through `textContent`)
- **ES modules**: native browser imports, component-per-file

### Infrastructure
- **PostgreSQL 16**: primary/replica streaming replication, pg_cron, pg_trgm, materialized views
- **Redis 7**: caching (3-day TTL, LRU eviction, 64MB limit)
- **MinIO**: S3-compatible object storage, self-hosted
- **LibreTranslate**: self-hosted translation, ES↔EN only (`LT_LOAD_ONLY=en,es`)
- **Redpanda v24.2**: Kafka-compatible broker, StatefulSet, persistent storage
- **Temporal 1.24**: durable workflow execution, PostgreSQL persistence
- **k3s**: single-node Kubernetes
- **Nginx**: TLS termination, HTTP→HTTPS redirect, HTTP/2, gzip, rate limiting, security headers
- **Let's Encrypt**: automated TLS via certbot, auto-renewed via cron

### Observability
- **Grafana**: live dashboard, publicly accessible with rotating demo credentials
- **Loki**: log aggregation
- **Promtail**: scrapes `temporal-worker` pod logs only, routes to Loki

### AI/ML
- **TensorFlow 2.15** + **OpenNSFW2**: automated content moderation on upload
- **Pillow**: image validation and optimization

---

## 🔍 How Things Work

### PostgreSQL Replication
Write pool connects to `postgres-primary`, read pool connects to `postgres-replica`. On startup the app calls **`pg_is_in_recovery()`** to verify the replica is actually in standby mode and falls back to primary for reads if it isn't.

### Search
Materialized view (`proveo.company_search`) with a **GIN trigram index**. Short queries (`< 4 chars`) use **`ILIKE`**, longer ones use **`similarity()`** scoring. **pg_cron** refreshes the view every minute with **`REFRESH MATERIALIZED VIEW CONCURRENTLY`** so reads are never blocked.

### Image Service
Separate microservice with its own Dockerfile and deployment. Validates format, dimensions, and content moderation score before writing to MinIO. Circuit breaker pattern prevents cascade failures if the service is unavailable. Images stream directly, no full file buffering in the backend.

### Kafka + Temporal Pipeline
Login and logout events publish to Redpanda, partitioned by language (`es → 0`, `en → 1`) to demonstrate deterministic routing and consumer locality. In a high-scale production environment, `user_uuid` would be used instead to ensure even distribution across partitions. A consumer worker routes events to Temporal's `AuthEventWorkflow`, which logs the event and fires a child `SendNotificationWorkflow` with **ABANDON policy**: the child keeps running after the parent completes.

Events are published via `asyncio.create_task` for sub-millisecond API response times — the HTTP response returns before Redpanda acknowledgment. For critical-path events where zero-loss is mandated over latency, `await` would be used to ensure delivery before responding. The rest of the wiring is production-grade: explicit partition routing, **manual offset commits** for **at-least-once delivery**, **deterministic workflow IDs** so duplicate Kafka delivery doesn't execute the workflow twice, fire-and-forget child workflows. Swap the mock email activity for a real one and the pipeline is production-ready.

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
Vanilla ES6+, no framework, no build step. Components rebuild on state change by clearing and reconstructing the DOM, straightforward and fast for this scale.

---

## ⚠️ Known Gaps

- One environment. No dev/staging split.
- CI/CD is scoped to `prod-*` commit prefixes via GitHub Actions: not a full pipeline.
- No backups. Local-path PVCs on one node: if the droplet dies, data goes with it.
- Single point of failure. Single-node k3s means no high availability: if the droplet goes down, the entire stack goes down with it. Remediation: in a production environment this would be deployed across a managed Kubernetes control plane (EKS/GKE) with a multi-AZ node group.
- `force_rollback` on DB methods is a testing convenience, not a production pattern.

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

The full production stack runs on Kubernetes, see the [Kubernetes Deployment Guide](./k8s%20scripts/README.md) for that. If you want a quick local look at the core app (no Kafka, no content moderation model, no k8s), use this earlier snapshot:

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
├── image-service/               # Content moderation microservice
│   ├── main.py                  # FastAPI + TensorFlow
│   ├── image_validator.py       # Image processing logic
│   └── config.py                # Service configuration
│
├── k8s/                         # Kubernetes manifests
│   ├── 00-namespace.yaml        # portfolio namespace
│   ├── 01-configmap.yaml        # app configuration
│   ├── 02-secrets.yaml          # secret template, auto-generated by deploy script
│   ├── 03-pvcs.yaml             # persistent storage (postgres, redis, minio)
│   ├── 04-postgres-primary.yaml # write database, WAL streaming source
│   ├── 05-postgres-replica.yaml # read replica, hot standby
│   ├── 06-redis.yaml            # cache, LRU eviction, 64MB cap
│   ├── 07-minio.yaml            # S3-compatible object storage
│   ├── 08-image-service.yaml    # content moderation microservice, TensorFlow
│   ├── 09-backend.yaml          # FastAPI app, migrations via initContainer
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
│   ├── init-ssl.sh              # certbot + Let's Encrypt setup, TLS secret injection into k3s
│   └── init-pgpass.sh
│
├── docker-compose.yml           # Local development
├── SSL_SETUP.md                 # Guide to install https
└── README.md
```

---

## 📬 Contact

**Andrés Olguín**

Email: acos2014600836@gmail.com

LinkedIn: https://www.linkedin.com/in/uwuolguin/

GitHub: https://github.com/uwuolguin/