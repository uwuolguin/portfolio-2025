# Proveo: B2B Provider Marketplace

## Live Demo

| URL | What |
|-----|------|
| [https://testproveoportfolio.xyz/front-page/front-page.html](https://testproveoportfolio.xyz/front-page/front-page.html) | Frontend |
| [https://testproveoportfolio.xyz/grafana](https://testproveoportfolio.xyz/grafana) | Grafana: live pipeline logs |

**Try the live pipeline:** Sign up and log in on the frontend, open Grafana and your login event will show up in the dashboard within seconds -- if it doesn't, refresh the Grafana tab.

**Grafana demo credentials:**

> **Username:** `demo`
> **Password:** `demo`

**A few things to know before poking around:**
- Email verification uses the Resend free tier, so only the email acos2014600836@gmail.com can receive the verification link. Company creation is restricted to admin-verified users for now, but you can still sign up.
- Private/incognito window recommended. Use passwords that do not relate to the ones you normally use, even though passwords are hashed.

---

## What This Is

A full-stack marketplace platform consolidating five years of professional experience into a single deployable project. Every component in this stack reflects tools used in production at some point in my career: PostgreSQL replication, Kafka event streaming, Temporal workflows, Kubernetes, Automated Content Moderation (Computer Vision), and observability.

The domain is a B2B marketplace where companies list their services. Simple enough to build as a side project, with enough operational surface area to make the infrastructure decisions meaningful.

Runs on a single DigitalOcean droplet (4GB RAM, 2 AMD vCPUs, 60GB SSD). No dev/staging split, one environment, manual deploys, except for commits prefixed with `prod-`, which trigger a GitHub Actions pipeline that runs the deployment scripts automatically. The prefix-based trigger avoids burning GitHub Actions minutes on work-in-progress commits.

---

## Architecture

### Services Overview

> Every service runs inside a single Kubernetes namespace (portfolio) on k3s, connected via ClusterIP. Nothing reaches the internet except through nginx.

```
Internet
   |
   |
   |  port 80 (HTTP)
   v
nginx on port 80 ───────────────────────────────────────────────────────────────────
   |
   |  /.well-known/acme-challenge/
   |    → serves Let's Encrypt challenge files so the SSL cert can renew itself
   |    → the only reason port 80 exists at all
   |
   |  everything else on port 80
   |    → hard redirect to HTTPS, no exceptions
   |
   |────────────────────────────────────────────────────────────────────────────────
   |
   |
   |  port 443 (HTTPS — the only port where real traffic flows)
   v
nginx on port 443 ──────────────────────────────────────────────────────────────────
   |
   |  ~/\.  (dot-files: www.domain.com/\.git)
   |    → blocked immediately, nobody should be hitting .git or .env
   |
   |  ~/api/v1/users/(login|signup|resend-verification)
   |    → goes to the FastAPI backend
   |    → auth gets its own stricter rules before the general /api/ block
   |    → smaller body limit, longer timeout (bcrypt hashing + email sending is slow)
   |
   |  /api/
   |    → goes to the FastAPI backend — this is where everything happens:
   |    →   database reads/writes, image uploads, search, user management
   |    →   the backend then talks to postgres, redis, minio, image-service, libretranslate
   |    → trailing slash stripped here to avoid FastAPI redirect stripping your cookies
   |
   |  /images/
   |    → goes straight to the image service, backend never sees this request
   |    → fetching a company photo: browser → nginx → image-service → MinIO → back
   |    → note: frontend appends ?v=timestamp on every render, so no browser caching
   |
   |  /docs  and  /openapi.json
   |    → goes to the FastAPI backend
   |    → just the Swagger UI, only available when DEBUG=true
   |
   |  /grafana/
   |    → goes to Grafana, which connects to Loki for logs
   |    → Loki gets logs from Alloy, which tails the temporal-worker pod
   |    → so: browser → nginx → grafana → loki → (logs from the event pipeline)
   |    → WebSocket kept alive so the dashboard updates in real time
   |
   |  /files/logos/  and  /files/test_pictures/
   |    → served directly from inside the nginx container, no service involved
   |    → logos: 30-day immutable cache, filename rename required to bust it
   |    → test pictures: 1-day cache, browser revalidates after expiry
   |    → no automated cache busting — manual filename rename on update
   |
   |  /health
   |    → nginx answers this itself, no upstream
   |    → Kubernetes hits this to know if nginx is alive
   |
   |  /  (everything else)
   |    → served directly from inside the nginx container
   |    → this is the entire frontend: HTML, CSS, vanilla JS
   |    → once the browser has these files, it starts calling /api/ on its own
   |
   |────────────────────────────────────────────────────────────────────────────────
```

---

This project runs 15 microservices by Peter Rodgers' original 2005 definition: a fine-grained service that does one thing, is network-accessible, and is independently deployable. The choice was deliberate, not because a marketplace needs this level of decomposition, but because at 15 services you start seeing the patterns you actually encounter in large corporate environments: Kafka + Temporal pipelines, PostgreSQL replication, and the operational overhead that comes with it (like debugging across multiple containers). That is exactly the point of this project, to reflect conditions close to what you find in production systems.

> **Note:** the stack counts as 15 not 16 because postgres-replica is the same PostgreSQL process as the primary running in standby mode, a real-time mirror with no independent capability, not a separate service, just high availability infrastructure for the primary.

---

### What the Backend Actually Talks To

> When a request reaches `/api/`, the FastAPI backend is the coordinator. It does not do everything itself — it delegates to specialized services depending on what the request needs.

```
FastAPI backend
   |
   |  every write (INSERT, UPDATE, DELETE)
   |    → PostgreSQL primary
   |    → the only node that accepts writes
   |    → also runs pg_cron to refresh the search materialized view every minute
   |
   |  every read (SELECT, search)
   |    → PostgreSQL replica
   |    → hot standby, streaming WAL from primary in real time
   |    → falls back to primary automatically if replica is unavailable
   |
   |  caching + rate limiting
   |    → Redis
   |    → products and communes cached for 3 days (they rarely change)
   |    → rate limiting counters also live here, per-IP sliding window
   |
   |  company image upload
   |    → Image Service (separate microservice)
   |    → validates format, dimensions, runs NSFW detection via TensorFlow
   |    → if it passes, stores the file in MinIO (S3-compatible object storage)
   |    → backend never buffers the file — streams directly through
   |
   |  company description translation
   |    → LibreTranslate (self-hosted, ES <-> EN only)
   |    → if you submit a description in Spanish, the backend translates to English
   |    → both versions stored in the database so search works in either language
   |
   |  login / logout events (fire-and-forget, does not block the response)
   |    → Redpanda (Kafka-compatible broker)
   |    → handed off to the async event pipeline
   |    → see the Auth Event Pipeline diagram below
```

---

### End-to-End Event Flow: Auth Event Pipeline

> A user logs in or out -> the event travels through four decoupled layers before producing a structured audit log and a (mock) notification email. Zero synchronous coupling between any of them.

```
User login / logout
      |
      v
FastAPI backend
  publishes event to Redpanda (fire-and-forget via asyncio.create_task)
  topics: user-logins - user-logouts
  partition key: lang (es -> p0, en -> p1)
      |
      v
Redpanda  ---- single-broker StatefulSet, 2 partitions/topic, 24 h retention
               partitioned by lang to demonstrate deterministic routing and consumer
               locality; in high-scale production use user_uuid instead
      |
      v
Consumer (aiokafka)
  polls Redpanda, deserialises event, commits offset only after hand-off succeeds
  at-least-once delivery guarantee
      |
      v
Temporal server  ---- durable workflow engine backed by PostgreSQL
  receives: StartWorkflow(AuthEventWorkflow, payload)
      |
      v
Temporal worker (portfolio-backend image, different CMD)
  executes AuthEventWorkflow
      |
      |-->  log_event_activity
      |       structlog -> JSON line -> stdout
      |                                |
      |                                v
      |                         Alloy
      |                           tails pod logs via Kubernetes API
      |                                |
      |                                v
      |                           Loki  ---- indexes JSON fields (level, event,
      |                                      workflow_id, event_type, lang)
      |                                |
      |                                v
      |                           Grafana  ---- LogQL queries, label filters,
      |                                         Loki pre-wired as default datasource
      |
      +-->  send_mock_email_activity  (fire-and-forget child workflow)
              logs what WOULD be sent; swap for real Resend call in production
```

**Why each layer exists:**

- **Redpanda** decouples the HTTP request from all downstream processing. The API response returns instantly; the event pipeline runs asynchronously.
- **Consumer -> Temporal hand-off** makes the workflow durable. If the Temporal server restarts mid-execution, the workflow resumes from the last checkpoint. No event is lost.
- **Temporal** provides retries, timeouts, and full execution history without any custom retry logic in application code.
- **Alloy -> Loki -> Grafana** gives observability into workflow execution without instrumenting the application beyond `structlog` JSON output.

---

## Stack

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
- **LibreTranslate**: self-hosted translation, ES<->EN only (`LT_LOAD_ONLY=en,es`)
- **Redpanda v24.2**: Kafka-compatible broker, StatefulSet, persistent storage
- **Temporal 1.24**: durable workflow execution, PostgreSQL persistence
- **k3s**: single-node Kubernetes
- **Nginx**: TLS termination, HTTP->HTTPS redirect, HTTP/2, gzip, rate limiting, security headers
- **Let's Encrypt**: automated TLS via certbot, auto-renewed via cron

### Observability
- **Grafana**: live dashboard, publicly accessible with static demo credentials
- **Loki**: log aggregation
- **Alloy**: scrapes `temporal-worker` pod logs only via Kubernetes API, routes to Loki

### AI/ML
- **TensorFlow 2.15** + **OpenNSFW2**: automated content moderation on upload
- **Pillow**: image validation and optimization

---

## How Things Work

### PostgreSQL Replication
Write pool connects to `postgres-primary`, read pool connects to `postgres-replica`. On startup the app calls **`pg_is_in_recovery()`** to verify the replica is actually in standby mode and falls back to primary for reads if it isn't.

### Search
Materialized view (`proveo.company_search`) with a **GIN trigram index**. Short queries (`< 4 chars`) use **`ILIKE`**, longer ones use **`similarity()`** scoring. **pg_cron** refreshes the view every minute with **`REFRESH MATERIALIZED VIEW CONCURRENTLY`** so reads are never blocked.

### Image Service
Separate microservice with its own Dockerfile and deployment. Validates format, dimensions, and content moderation score before writing to MinIO. Circuit breaker pattern prevents cascade failures if the service is unavailable. Images stream directly, no full file buffering in the backend.

### Kafka + Temporal Pipeline
Login and logout events publish to Redpanda, partitioned by language (`es -> 0`, `en -> 1`) to demonstrate deterministic routing and consumer locality. In a high-scale production environment, `user_uuid` would be used instead to ensure even distribution across partitions. A consumer worker routes events to Temporal's `AuthEventWorkflow`, which logs the event and fires a child `SendNotificationWorkflow` with **ABANDON policy**: the child keeps running after the parent completes.

Events are published via `asyncio.create_task` for sub-millisecond API response times. The HTTP response returns before Redpanda acknowledgment. For critical-path events where zero-loss is mandated over latency, `await` would be used to ensure delivery before responding. The rest of the wiring is production-grade: explicit partition routing, **manual offset commits** for **at-least-once delivery**, **deterministic workflow IDs** so duplicate Kafka delivery doesn't execute the workflow twice, fire-and-forget child workflows. Swap the mock email activity for a real one and the pipeline is production-ready.

### Live Pipeline Verification: Grafana
Go to `https://testproveoportfolio.xyz/grafana` and log in with the demo credentials: username `demo`, password `demo`. Then create an account on the demo site and log in. The event shows up in the dashboard within seconds -- if it doesn't, refresh the Grafana tab.

What you'll see:
- `event_type`: login or logout
- `email`: the account that triggered the event (anonymous for logouts)
- `lang`: language the user was browsing in (es or en)
- `partition`: which Redpanda partition received the event (es -> 0, en -> 1)

Full chain: login endpoint -> `asyncio.create_task(kafka_producer.publish_event(...))` -> Redpanda -> consumer offset commit -> Temporal `AuthEventWorkflow` -> `log_event_activity` -> structlog JSON -> Alloy scrapes `temporal-worker` via Kubernetes API -> Loki -> Grafana.

### TLS
Certbot provisions Let's Encrypt certs on the droplet, they get copied to `/home/deploy/certs/` and loaded into Kubernetes as a `tls-secret`. Nginx terminates TLS, sets `X-Forwarded-Proto: https`. Root cron job handles renewal: updates the secret and restarts nginx.

### Structured Logging
Every caught exception across every service is JSON via structlog. In the `temporal-worker` pod specifically, uncaught exceptions are also captured as JSON: asyncio loop exceptions via `install_async_exception_handler` and synchronous crashes via `sys.excepthook`. Temporal SDK Python-side logs and Rust core logs are routed through `LogForwardingConfig` and formatted as JSON in that same pod. Gaps: threads, multiprocessing, and OS-level errors that occur before the asyncio worker starts (such as missing env vars resolved at import time) are not guaranteed to be JSON. The `temporal-worker` pod logs are scraped by Alloy and indexed in Loki: queryable live in Grafana.

### Frontend
Vanilla ES6+, no framework, no build step. Components rebuild on state change by clearing and reconstructing the DOM, straightforward and fast for this scale.

---

## Architectural Trade-offs & Future Roadmap

- One environment. No dev/staging split.
- CI/CD is scoped to `prod-*` commit prefixes via GitHub Actions: not a full pipeline.
- No backups. Local-path PVCs on one node: if the droplet dies, data goes with it.
- Single point of failure. Single-node k3s means no high availability: if the droplet goes down, the entire stack goes down with it. Remediation: in a production environment this would be deployed across a managed Kubernetes control plane (EKS/GKE) with a multi-AZ node group.
- Inline documentation: Manifests and scripts have comments explaining non-obvious values or why a particular configuration was chosen. The goal for this repo is that every config value that isn't self-evident has a comment next to it.
- `force_rollback` on DB methods is a testing convenience, not a production pattern.
- **Single-namespace monitoring**: Grafana, Loki, and Alloy run inside the `portfolio` namespace alongside the application. In a real multi-tenant environment, observability infrastructure lives in a dedicated `monitoring` namespace - the same Grafana/Loki stack then serves `portfolio`, `staging`, `payments`, or any other namespace without being coupled to one application. The mechanics: Alloy's `ClusterRole` grants `get/watch/list` on pods cluster-wide, and the `ClusterRoleBinding` maps that role to the `alloy` ServiceAccount in `monitoring`, so it can tail logs from every namespace while running in its own. Keeping them separate also means you can wipe `kubectl delete namespace portfolio` during a clean deploy cycle without taking down observability. For this single-environment demo the separation adds DNS complexity (`loki.monitoring.svc.cluster.local` vs `loki.portfolio.svc.cluster.local`) with no operational benefit, so everything lives in `portfolio`.

---

## Pod Breakdown (4GB Droplet)

| Pod | Manifest | Actual RAM |
|-----|----------|-----------|
| `postgres-primary-0` | `04-postgres-primary.yaml` | ~83Mi |
| `postgres-replica-0` | `05-postgres-replica.yaml` | ~49Mi |
| `redis-*` | `06-redis.yaml` | ~6Mi |
| `minio-*` | `07-minio.yaml` | ~86Mi |
| `image-service-*` | `08-image-service.yaml` | ~367Mi |
| `backend-*` | `09-backend.yaml` | ~75Mi |
| `nginx-*` | `10-nginx.yaml` | ~4Mi |
| `redpanda-0` | `11-redpanda.yaml` | ~300Mi |
| `consumer-*` | `13-consumer.yaml` | ~25Mi |
| `temporal-*` | `14-temporal.yaml` | ~91Mi |
| `temporal-ui-*` | `14-temporal.yaml` | ~7Mi |
| `temporal-worker-*` | `15-temporal-worker.yaml` | ~50Mi |
| `libretranslate-*` | `16-libretranslate.yaml` | ~560Mi |
| `loki-*` | `17-monitoring.yaml` | ~58Mi |
| `alloy-*` | `17-monitoring.yaml` | ~45Mi |
| `grafana-*` | `17-monitoring.yaml` | ~86Mi |
| **Subtotal (pods)** | | **~1,892Mi** |
| **System overhead** | k3s, containerd, dockerd, journald | **~1,131Mi** |
| **Process total** | matches `free -h` used | **~3,023Mi (~3.0GB, 74%)** |
| | | |
| **buff/cache** | The kernel uses buff/cache to store frequently accessed data from disk in RAM so it does not have to read from disk again. The more of it there is, the faster the system feels. It gets freed automatically when a process needs more RAM, so it is never wasted. Trying to clear it manually gives a false sense of free memory and actually slows the system down. | **~1,638Mi** |
| **Available** | RAM Linux can hand out before touching swap | **~1,434Mi** |
| **Swap used / total** | system is already dipping into swap under low traffic, a signal, not an alarm | **215Mi / 2,048Mi** |
| **Total RAM** | | **3,891Mi (3.8GB physical)** |

### Sizing Takeaway

| Scenario | Recommendation |
|----------|---------------|
| **Replicate this exact stack** | 4GB is the absolute minimum. The system is already using 215Mi of swap under low traffic, which means there is no real headroom. A minimum of **6GB is recommended** to keep the stack stable without relying on swap. |
| **Add one more heavy service** | **8GB** is recommended. buff/cache will compete for the remaining available RAM under any meaningful load. |
| **Production with real traffic** | **8GB minimum**, ideally **16GB**. Traffic spikes cause PostgreSQL and Redpanda to buffer aggressively, and the kernel cache needs room to stay warm rather than get evicted. |
| **Could this run on 2GB?** | No. Process usage alone is ~3.0GB under low traffic; the system would be deep in swap and performance would degrade badly. |

---

## Quick Local Preview

The full production stack runs on Kubernetes, see the [Kubernetes Deployment Guide](./k8s%20scripts/README.md) for that. If you want a quick local look at the core app (no Kafka, no temporal, no k8s), use this earlier snapshot:

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

## Project Structure

```
proveo/
|-- .github/
|   |-- workflows/
|   |   |-- deploy.yml           # Triggers on prod-* commits, SSHs into droplet and runs deploy scripts
|   |   |-- eslint.yml           # Triggers on prod-* or dopkp commits, runs ESLint on frontend JS
|   |   |-- pylint_backend.yml   # Triggers on prod-* or dopkp commits, runs pylint on backend/app
|   |   +-- pylint_image_service.yml  # Triggers on prod-* or dopkp commits, runs pylint on image-service
|
|-- backend/                      # FastAPI application
|   |-- app/
|   |   |-- database/            # Read/write pools, transactions
|   |   |-- routers/             # API endpoints
|   |   |-- auth/                # JWT + CSRF
|   |   |-- services/            # Image processing, email, translation, circuit breaker
|   |   |-- schemas/             # Pydantic models
|   |   |-- middleware/          # CORS, logging, security
|   |   |-- redis/               # Cache, rate limiting
|   |   |-- kafka/               # Redpanda producer + consumer worker
|   |   |-- temporal/            # Workflows, activities, worker
|   |   |-- templates/           # Email HTML templates
|   |   |-- utils/               # Validators, exceptions
|   |   +-- tests/               # Pytest test suite
|   |-- Dockerfile
|   |-- alembic/                 # Database migrations
|   +-- scripts/                 # Admin tools, seeding, maintenance
|
|-- image-service/               # Content moderation microservice
|   |-- main.py                  # FastAPI + TensorFlow
|   |-- image_validator.py       # Image processing logic
|   |-- Dockerfile
|   +-- config.py                # Service configuration
|
|-- k8s/                         # Kubernetes manifests
|   |-- 00-namespace.yaml        # portfolio namespace
|   |-- 01-configmap.yaml        # app configuration
|   |-- 02-secrets.yaml          # secret template, auto-generated by deploy script
|   |-- 03-pvcs.yaml             # persistent storage (postgres, redis, minio)
|   |-- 04-postgres-primary.yaml # write database, WAL streaming source
|   |-- 05-postgres-replica.yaml # read replica, hot standby
|   |-- 06-redis.yaml            # cache, LRU eviction, 64MB cap
|   |-- 07-minio.yaml            # S3-compatible object storage
|   |-- 08-image-service.yaml    # content moderation microservice, TensorFlow
|   |-- 09-backend.yaml          # FastAPI app, migrations via initContainer
|   |-- 10-nginx.yaml            # TLS termination + HTTP->HTTPS redirect
|   |-- 11-redpanda.yaml         # Kafka-compatible broker (StatefulSet)
|   |-- 12-redpanda-init.yaml    # One-shot Job, creates topics after broker ready
|   |-- 13-consumer.yaml         # Redpanda consumer, routes events to Temporal
|   |-- 14-temporal.yaml         # Temporal server + UI
|   |-- 15-temporal-worker.yaml  # Temporal worker (AuthEventWorkflow)
|   |-- 16-libretranslate.yaml   # Self-hosted translation service (ES<->EN)
|   +-- 17-monitoring.yaml       # Grafana + Loki + Alloy (temporal-worker logs only)
|
|-- k8s scripts/                 # Deployment automation
|   |-- 00-install-k3s.sh
|   |-- build-and-import-k3s.sh
|   |-- deploy-k3s-local.sh
|   |-- set-resend-key.sh
|   |-- cleanup.sh
|   |-- USEFULCOMMANDS.md        # Server exploration, SSH hardening
|   +-- README.md                # K8s deployment guide
|
|-- nginx/                       # Reverse proxy + frontend
|   |-- nginx.conf               # Local dev config (Docker Compose)
|   |-- Dockerfile
|   +-- frontend/                # Static files
|
|-- postgres/                    # Custom PostgreSQL image
|   |-- Dockerfile
|   |-- init-db.sh               # Creates temporal and temporal_visibility databases
|   |-- init-ssl.sh              # Configures SSL using pre-mounted certs (postgresql.ssl.conf + pg_hba symlink)
|   +-- init-pgpass.sh           # passwordless non-interactive connections
|
|-- docker-compose.yml           # Local development
|-- SSL_SETUP.md                 # Guide to install https
|-- eslint.config.mjs
+-- README.md
```

---

## Contact

**Andres Olguin**

Email: acos2014600836@gmail.com

LinkedIn: https://www.linkedin.com/in/uwuolguin/

GitHub: https://github.com/uwuolguin/