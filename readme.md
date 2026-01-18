# 🚀 Proveo - B2B Provider Marketplace Platform
+
A full-stack marketplace platform connecting businesses with service providers. Built with modern technologies focusing on scalability, security, and performance.

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [🛠️ Tech Stack](#️-tech-stack)
- [🚀 Getting Started](#-getting-started)
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
- **Database connection pooling** with health monitoring and retry logic
- **Redis caching** with graceful degradation when unavailable
- **Rate limiting** (per-IP and global) with Redis-backed counters
- **Structured JSON logging** with correlation IDs for request tracing
- **Docker multi-container orchestration** with health checks
- **Automated database migrations** (Alembic)
- **Background job scheduling** (APScheduler) for maintenance tasks

---

## 🏗️ Architecture

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
   - PostgreSQL query (connection pool)
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
- **Docker Compose** - Multi-container orchestration
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

### Quick Start

#### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/proveo.git
cd proveo
```

#### 2. Create Environment File
```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# ============================================================================
# Database Configuration
# ============================================================================
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_ultra_secure_password_here_min_20_chars
POSTGRES_DB=portfolio

# Database connection strings (auto-generated from above)
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}?ssl=require
ALEMBIC_DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}?sslmode=require

# ============================================================================
# Security & JWT
# ============================================================================
# Generate with: openssl rand -hex 32
SECRET_KEY=your_jwt_secret_key_64_characters_minimum_random_hex_string_here

# Generate with: openssl rand -hex 32
ADMIN_API_KEY=your_admin_api_key_for_csrf_bypass_development_only

# Comma-separated list of IPs allowed to use admin bypass (development only)
ADMIN_BYPASS_IPS=127.0.0.1,172.18.0.1

# JWT settings
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120

# ============================================================================
# Redis
# ============================================================================
REDIS_URL=redis://redis:6379/0
CACHE_TTL=3600

# ============================================================================
# MinIO (S3-Compatible Storage)
# ============================================================================
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin_change_in_production
MINIO_ENDPOINT=minio:9000
MINIO_BUCKET=images
MINIO_SECURE=false

# ============================================================================
# Email Configuration (Resend)
# ============================================================================
# Get free API key from: https://resend.com
RESEND_API_KEY=re_your_resend_api_key_here
ADMIN_EMAIL=admin@yourdomain.com
EMAIL_FROM=noreply@yourdomain.com

# Email verification token expiry (hours)
VERIFICATION_TOKEN_EMAIL_TIME=24

# ============================================================================
# Application Settings
# ============================================================================
API_BASE_URL=http://localhost
DEBUG=true
PROJECT_NAME=Proveo API

# CORS allowed origins (comma-separated, no wildcards in production)
ALLOWED_ORIGINS=http://localhost,http://localhost:80

# ============================================================================
# Image Service
# ============================================================================
IMAGE_SERVICE_URL=http://image-service:8080
MAX_FILE_SIZE=10000000
NSFW_ENABLED=true
NSFW_THRESHOLD=0.75
```

#### 3. Start the Application
```bash
# Start all containers
docker compose up -d

# View logs
docker compose logs -f
```

#### 4. Initialize the Database & Seed Data for Testing Purposes
```bash
# Run migrations
docker compose exec backend alembic upgrade head

# Set up pg_cron job for materialized view refresh
docker compose exec backend python -m scripts.database.manage_search_refresh_cron

# Seed test data (16 users with companies + 1 admin)
docker compose exec backend python -m scripts.database.seed_test_data

# Or use PowerShell script (Windows):
.\init_demo.ps1
```

#### 5. Access the Application
- **Frontend**: http://localhost/front-page/front-page.html
- **API Docs (Swagger)**: http://localhost/docs
- **API Docs (ReDoc)**: http://localhost/redoc
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)

#### 6. Test Login Credentials

**Admin Account:**
- Email: `admin_test@mail.com`
- Password: `password`

**Test Users (16 accounts):**
- Email: `testuser01@proveo.com` through `testuser16@proveo.com`
- Password: `TestPass123!` (all users)
- All test users have verified emails and associated companies

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
  │                    ├─Create user──────>│                    │
  │                    │                   │                    │
  │                    ├─Send verification email───────────────>│
  │<───201 Created─────┤                   │                    │
  │                    │                   │                    │
  ├─GET /verify/{token}│                   │                    │
  │                    ├─Update verified──>│                    │
  │<───HTML success────┤                   │                    │
  │                    │                   │                    │
  ├─POST /login───────>│                   │                    │
  │                    ├─Verify creds─────>│                    │
  │<───JWT+CSRF─────────┤                   │                    │
  │                    │                   │                    │
  ├─POST /companies───>│                   │                    │
  │ (with CSRF header) │                   │                    │
  │                    ├─Validate JWT+CSRF │                    │
  │                    ├─Create company───>│                    │
  │<───201 Created─────┤                   │                    │
```

### Key Endpoints

#### Authentication & User Management
```http
POST   /api/v1/users/signup                    # Register new account
GET    /api/v1/users/verify-email/{token}      # Verify email (HTML response)
POST   /api/v1/users/resend-verification       # Resend verification email
POST   /api/v1/users/login                     # Login (returns JWT + CSRF token)
POST   /api/v1/users/logout                    # Logout (clears cookies)
GET    /api/v1/users/me                        # Get current user info
DELETE /api/v1/users/me                        # Delete own account (cascades)
```

#### Companies (Public)
```http
GET    /api/v1/companies/search                # Search companies
       ?q=keyword                               # Search text
       &commune=Santiago                        # Filter by commune
       &product=Technology                      # Filter by product
       &lang=es                                 # Response language (es/en)
       &limit=20                                # Results per page
       &offset=0                                # Pagination offset

GET    /api/v1/companies/{uuid}                # Get company by ID
```

#### Companies (Authenticated - Email Verified Required)
```http
GET    /api/v1/companies/user/my-company       # Get my company
POST   /api/v1/companies                       # Create company (multipart/form-data)
PATCH  /api/v1/companies/user/my-company       # Update my company
DELETE /api/v1/companies/user/my-company       # Delete my company
```

**Create Company Request (multipart/form-data):**
```javascript
const formData = new FormData();
formData.append('name', 'Tech Solutions SA');
formData.append('commune_name', 'Santiago Centro');
formData.append('product_name', 'Tecnología');
formData.append('address', 'Av. Providencia 1234');
formData.append('phone', '+56912345678');
formData.append('email', 'contact@techsolutions.cl');
formData.append('description_es', 'Soluciones tecnológicas');
formData.append('description_en', 'Tech solutions');
formData.append('image', fileInput.files[0]);
formData.append('lang', 'es');

fetch('/api/v1/companies', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'X-CSRF-Token': localStorage.getItem('csrf_token')
  },
  body: formData
});
```

#### Products (Public Read, Admin Write)
```http
GET    /api/v1/products/                       # List all products
POST   /api/v1/products/use-postman-or-similar-to-bypass-csrf
PUT    /api/v1/products/{uuid}/use-postman-or-similar-to-bypass-csrf
DELETE /api/v1/products/{uuid}/use-postman-or-similar-to-bypass-csrf
```

#### Communes (Public Read, Admin Write)
```http
GET    /api/v1/communes/                       # List all communes
POST   /api/v1/communes/use-postman-or-similar-to-bypass-csrf
PUT    /api/v1/communes/{uuid}/use-postman-or-similar-to-bypass-csrf
DELETE /api/v1/communes/{uuid}/use-postman-or-similar-to-bypass-csrf
```

#### Admin Only
```http
GET    /api/v1/users/admin/all-users/use-postman-or-similar-to-bypass-csrf
       ?limit=100&offset=0
DELETE /api/v1/users/admin/users/{uuid}/use-postman-or-similar-to-bypass-csrf

GET    /api/v1/companies/admin/all-companies/use-postman-or-similar-to-bypass-csrf
       ?limit=100&offset=0
DELETE /api/v1/companies/admin/companies/{uuid}/use-postman-or-similar-to-bypass-csrf
```

#### Health Checks
```http
GET    /api/v1/health/                         # Basic health check
GET    /api/v1/health/database                 # Database connection check
GET    /health                                 # Nginx health (returns "healthy")
```

### CSRF Protection

All state-changing operations (POST, PUT, PATCH, DELETE) require CSRF validation:

```javascript
// 1. Get CSRF token from login response
const response = await fetch('/api/v1/users/login', {
  method: 'POST',
  credentials: 'include',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
});

const data = await response.json();
localStorage.setItem('csrf_token', data.csrf_token);

// 2. Include CSRF token in all mutation requests
await fetch('/api/v1/companies/', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'X-CSRF-Token': localStorage.getItem('csrf_token')
  },
  body: formData
});
```

**Admin Bypass (Development Only):**
```bash
# DO NOT USE IN PRODUCTION
curl -X POST http://localhost/api/v1/products/use-postman-or-similar-to-bypass-csrf \
  -H "X-Admin-Bypass-CSRF: your_admin_api_key" \
  -H "Content-Type: application/json" \
  -d '{"name_es": "Producto", "name_en": "Product"}'
```

---

## 📁 Project Structure

```
proveo/
├── backend/
│   ├── alembic/                          # Database migrations
│   │   ├── versions/                     # Migration files
│   │   │   ├── 2025_09_28_1733-*.py     # Initial schema
│   │   │   ├── 2025_09_28_2345-*.py     # Materialized view
│   │   │   ├── 2025_10_14_2153-*.py     # Business constraints
│   │   │   ├── 2025_10_20_2029-*.py     # RBAC + email verification
│   │   │   ├── 2025_11_17_0108-*.py     # Image extensions
│   │   │   └── 2026_01_11_0340-*.py     # pg_cron setup
│   │   ├── env.py                        # Alembic environment
│   │   └── script.py.mako                # Migration template
│   │
│   ├── app/
│   │   ├── auth/                         # Authentication & authorization
│   │   │   ├── csrf.py                   # CSRF token validation
│   │   │   ├── jwt.py                    # JWT operations
│   │   │   └── dependencies.py           # FastAPI dependencies
│   │   │
│   │   ├── database/
│   │   │   ├── connection.py             # Async connection pool
│   │   │   ├── transactions.py           # DB operations (transactional)
│   │   │   └── db_retry.py               # Retry logic with tenacity
│   │   │
│   │   ├── middleware/
│   │   │   ├── cors.py                   # CORS configuration
│   │   │   ├── logging.py                # Request/response logging
│   │   │   └── security.py               # Security headers (CSP, HSTS, etc.)
│   │   │
│   │   ├── redis/
│   │   │   ├── redis_client.py           # Redis connection manager
│   │   │   ├── cache_manager.py          # Cache invalidation logic
│   │   │   ├── decorators.py             # @cache_response
│   │   │   └── rate_limit.py             # Rate limiting with Redis
│   │   │
│   │   ├── routers/                      # API endpoints
│   │   │   ├── users.py                  # User management
│   │   │   ├── companies.py              # Company CRUD
│   │   │   ├── products.py               # Product management
│   │   │   ├── communes.py               # Commune/location management
│   │   │   └── health.py                 # Health check endpoints
│   │   │
│   │   ├── schemas/                      # Pydantic models
│   │   │   ├── models.py                 # SQLAlchemy models
│   │   │   ├── users.py                  # User request/response schemas
│   │   │   ├── companies.py              # Company schemas
│   │   │   ├── products.py               # Product schemas
│   │   │   └── communes.py               # Commune schemas
│   │   │
│   │   ├── services/
│   │   │   ├── email_service.py          # Resend email integration
│   │   │   ├── image_service_client.py   # Image service HTTP client
│   │   │   ├── translation_service.py    # Google Translate integration
│   │   │   └── circuit_breaker.py        # Circuit breaker pattern
│   │   │
│   │   ├── templates/
│   │   │   └── email_verification.py     # HTML email templates
│   │   │
│   │   ├── utils/
│   │   │   ├── exceptions.py             # Custom exception handlers
│   │   │   └── validators.py             # Input validation utilities
│   │   │
│   │   ├── tests/                        # Pytest test suite
│   │   │   ├── test_user.py
│   │   │   ├── test_company.py
│   │   │   ├── test_product.py
│   │   │   ├── test_commune.py
│   │   │   ├── test_health.py
│   │   │   ├── test_orphan_image_cleanup.py
│   │   │   └── test_refresh_materialized_view.py
│   │   │
│   │   ├── config.py                     # Pydantic settings
│   │   └── main.py                       # FastAPI app entry point
│   │
│   ├── scripts/
│   │   ├── admin/
│   │   │   └── create_admin.py           # Interactive admin creation
│   │   ├── database/
│   │   │   ├── seed_test_data.py         # Seed 16 users + companies
│   │   │   └── manage_search_refresh_cron.py  # pg_cron job management
│   │   └── maintenance/
│   │       └── cleanup_orphan_images.py  # Clean orphaned MinIO objects
│   │
│   ├── alembic.ini                       # Alembic configuration
│   ├── requirements.txt                  # Python dependencies
│   └── Dockerfile                        # Multi-stage build
│
├── image-service/                        # Dedicated image microservice
│   ├── config.py                         # Pydantic settings
│   ├── main.py                           # FastAPI app
│   ├── image_validator.py                # PIL + OpenNSFW2 validation
│   ├── requirements.txt                  # Includes TensorFlow
│   └── Dockerfile                        # Multi-stage build
│
├── postgres/
│   ├── init-ssl.sh                       # SSL certificate setup
│   ├── init-db.sh                        # Database creation
│   ├── init-pgpass.sh                    # Password file setup
│   └── Dockerfile                        # PostgreSQL 16 + pg_cron
│
├── nginx/
│   ├── nginx.conf                        # Reverse proxy configuration
│   ├── Dockerfile                        # Alpine-based image
│   └── frontend/                         # Static files (baked into image)
│       └── web-pages/
│           ├── 0-shared-components/
│           │   ├── header-nav-bar/
│           │   ├── footer/
│           │   └── utils/
│           │   |    └── shared-functions.js  # Auth helpers, API client
|           |   |    └── sanitizer.js  # XSS prevention, input sanitization, safe DOM manipulation
│           │   └── libs/
│           │       └── purify.min.js  # DOMPurify 3.0.8 - XSS sanitization library
│           ├── front-page/               # Home + search
│           ├── sign-up/                  # Registration form
│           ├── log-in/                   # Login form
│           ├── publish/                  # Create company form
│           ├── profile-view/             # Company profile view
│           └── profile-edit/             # Edit company form
│
├── docker-compose.yml                    # Multi-container orchestration
├── init_demo.ps1                         # PowerShell init script
├── .env.example                          # Environment template
├── .gitignore
└── README.md
```

---

## 🔒 Security Features

### Authentication & Authorization
- **JWT tokens** stored in HTTP-only cookies (XSS protection)
- **CSRF tokens** required for all mutations (CSRF attack prevention)
- **bcrypt password hashing** with 12 rounds
- **Email verification** before account activation
- **Role-Based Access Control** (User/Admin)
  - Users can only modify their own data
  - Admins can manage all resources
- **Secure session management** with configurable token expiry

### Input Validation & Sanitization
- **Pydantic v2** for comprehensive request validation
- **Custom validators** for:
  - Email format (RFC 5322 compliance)
  - Phone numbers (E.164 format support)
  - Names (XSS pattern detection)
  - Descriptions (length limits)
  - Addresses (sanitization)
- **File upload validation**:
  - MIME type checking (JPEG/PNG only)
  - File size limits (10MB max)
  - Image dimension limits (4000x4000 max)
  - Format verification (PIL-based)
- **SQL injection prevention** (parameterized queries only)
- **Path traversal protection** (validated file paths)

### Content Moderation
- **OpenNSFW2 AI model** for inappropriate image detection
- **TensorFlow-based inference** (0.75 threshold)
- **Configurable fail-closed mode** (block if check fails)
- **Automatic rejection** of flagged content

### Infrastructure Security
- **Security headers**:
  - `Content-Security-Policy` (XSS mitigation)
  - `Strict-Transport-Security` (HTTPS enforcement)
  - `X-Frame-Options: DENY` (clickjacking prevention)
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- **Rate limiting**:
  - 20 requests/second per IP (global API)
  - 10 requests/second for static files
  - Redis-backed counters with sliding window
- **CORS** with explicit origin whitelist (no wildcards in production)
- **PostgreSQL SSL/TLS** support (certificate-based encryption)
- **Secrets management** (environment variables, never committed)
- **Database connection encryption** (sslmode=require)

### Audit & Monitoring
- **Structured JSON logging** with:
  - Correlation IDs for request tracing
  - User actions (create/update/delete)
  - Failed login attempts
  - Admin actions (with email logging)
  - Suspicious activity detection
- **Soft deletes** (audit trail preservation)
  - `users_deleted`, `companies_deleted`, etc.
  - Timestamp + original data retention
- **Health check endpoints** for monitoring
- **Database query logging** (slow query detection)

### Known Security Limitations (Portfolio Project)
⚠️ **CSRF Admin Bypass** - Must be removed for production
⚠️ **Default passwords** in `.env.example` - Change immediately
⚠️ **No WAF** - Consider adding Cloudflare or similar
⚠️ **No DDoS protection** - Rate limiting is basic
⚠️ **Self-signed SSL certs** - Use Let's Encrypt in production

---

## ⚡ Performance Optimizations

### Database Layer
- **asyncpg connection pooling**:
  - Min: 5 connections
  - Max: 20 connections
  - Max queries per connection: 50,000
  - Idle timeout: 300 seconds
- **Materialized views** for search:
  - Trigram indexing (GIN) for fuzzy matching
  - Concurrent refresh (non-blocking)
  - Auto-refresh via pg_cron (every minute)
- **Indexes**:
  - Primary keys (UUID)
  - Foreign keys
  - Unique constraints (email, product names)
  - GIN index on `searchable_text` column
- **Query optimizations**:
  - Parameterized queries (no ORM overhead)
  - SELECT only needed columns
  - Query timeout enforcement (60s)
  - Connection reuse (keep-alive)
- **Retry logic**:
  - Exponential backoff (0.5s base, 5s max)
  - 3 retry attempts
  - Handles transient errors (deadlocks, connection failures)

### Caching Strategy
- **Redis-backed caching**:
  - Products list: 3-day TTL (rarely changes)
  - Communes list: 3-day TTL (rarely changes)
  - Rate limit counters: 60-second TTL
- **Cache invalidation**:
  - Explicit invalidation on create/update/delete
  - Cache keys: `products:all`, `communes:all`
- **Graceful degradation**:
  - App continues if Redis unavailable
  - Logs warning but serves from database
  - No user-facing errors

### API Layer
- **Async operations** throughout:
  - asyncpg for database
  - httpx for HTTP client (image service)
  - Async file I/O
- **Pagination**:
  - Default: 20 items per page
  - Max: 500 items (admin endpoints)
  - Offset-based pagination
- **Connection pooling**:
  - Database: 20 max connections
  - HTTP client: 100 max connections
  - Keep-alive: 20 connections
- **Request correlation**:
  - Unique ID per request
  - Propagated through all services
  - Enables distributed tracing

### Frontend Optimizations
- **Component lazy loading** (dynamic imports)
- **LocalStorage caching**:
  - User session data
  - UI state
- **Optimized images**:
  - Automatic JPEG compression (90% quality)
  - PNG optimization (level 6)
  - RGBA→RGB conversion (smaller file size)
  - Max dimensions: 4000x4000
- **Static asset caching**:
  - Logos: 30-day cache
  - Images: 30-day cache
  - HTML/CSS/JS: No cache (development)

### Nginx Performance
- **Gzip compression** (level 6)
  - Enabled for: HTML, CSS, JS, JSON, XML, SVG
  - Min size: 1000 bytes
- **Keep-alive connections**:
  - Timeout: 15 seconds
  - Max requests: 100 per connection
- **Upstream connection pooling**:
  - Backend: 32 keep-alive connections
  - Image service: 32 keep-alive connections
- **Buffer optimization**:
  - Body: 1MB buffer
  - Headers: 1KB buffer
- **Timeouts**:
  - Client body: 10s
  - Client header: 10s
  - Send: 10s
  - Proxy read: 300s (for long uploads)

### Image Service Optimizations
- **Streaming uploads** (no intermediate buffering)
- **Single-pass processing**:
  - Validation → NSFW check → Storage (one file read)
- **Memory efficiency**:
  - BytesIO streams (no disk writes)
  - Stream reuse (no copying)
  - Memory usage: ~1x file size (vs. 4x in naive implementation)
- **Parallel processing** (async workers)
- **MinIO connection pooling**

---

## 💻 Development

### Local Development Setup

#### Option 1: Docker (Recommended)
```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f backend

# Run migrations
docker compose exec backend alembic upgrade head

# Access database
docker compose exec postgres psql -U postgres -d portfolio

# Access Redis CLI
docker compose exec redis redis-cli

# Shell into backend
docker compose exec backend /bin/bash
```

#### Option 2: Native Python (Backend Only)
```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/portfolio?sslmode=disable"
export REDIS_URL="redis://localhost:6379/0"
export SECRET_KEY="dev-secret-key-change-in-production"
export RESEND_API_KEY="your_api_key"
export IMAGE_SERVICE_URL="http://localhost:8080"

# Run migrations
alembic upgrade head

# Start development server (with auto-reload)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Development
```bash
# Serve with Python
cd nginx/frontend/web-pages
python -m http.server 3000

# Or use any static server
npx serve . -p 3000

# Access at http://localhost:3000
```

### Database Migrations

```bash
# Create new migration (auto-generate from models)
docker compose exec backend alembic revision --autogenerate -m "add_column_to_users"

# Create empty migration
docker compose exec backend alembic revision -m "custom_migration"

# Apply migrations
docker compose exec backend alembic upgrade head

# Rollback one migration
docker compose exec backend alembic downgrade -1

# Rollback to specific revision
docker compose exec backend alembic downgrade <revision_id>

# View migration history
docker compose exec backend alembic history

# View current revision
docker compose exec backend alembic current
```

### Admin User Management

```bash
# Interactive admin creation
docker compose exec backend python -m scripts.admin.create_admin

# Follow prompts to enter:
# - Email
# - Password (min 8 characters)
# - Name

# Or promote existing user to admin via SQL
docker compose exec postgres psql -U postgres -d portfolio -c \
  "UPDATE proveo.users SET role='admin', email_verified=true WHERE email='user@example.com';"
```

### Maintenance Jobs

```bash
# Clean up orphaned images (dry run - shows what would be deleted)
docker compose exec backend python -m scripts.maintenance.cleanup_orphan_images

# Manually refresh materialized view
docker compose exec postgres psql -U postgres -d portfolio -c \
  "REFRESH MATERIALIZED VIEW CONCURRENTLY proveo.company_search;"

# Reset pg_cron job (if it gets duplicated)
docker compose exec backend python -m scripts.database.manage_search_refresh_cron

# View pg_cron jobs
docker compose exec postgres psql -U postgres -d portfolio -c \
  "SELECT * FROM cron.job;"

# View pg_cron run history
docker compose exec postgres psql -U postgres -d portfolio -c \
  "SELECT * FROM cron.job_run_details ORDER BY start_time DESC LIMIT 10;"
```

### Useful Commands

```bash
# View container logs
docker compose logs -f [service_name]

# Restart specific service
docker compose restart backend

# Rebuild and restart after code changes
docker compose up -d --build backend

# Access container shell
docker compose exec backend /bin/bash
docker compose exec postgres /bin/bash

# Check container health
docker compose ps

# View resource usage
docker stats

# Clean up everything (⚠️ DESTROYS ALL DATA)
docker compose down -v --remove-orphans

# Database backup
docker compose exec postgres pg_dump -U postgres portfolio > backup.sql

# Database restore
docker compose exec -T postgres psql -U postgres portfolio < backup.sql

# Export MinIO images
docker compose exec minio mc cp --recursive /data/images ./minio-backup/

# View Redis keys
docker compose exec redis redis-cli KEYS "*"

# Clear Redis cache
docker compose exec redis redis-cli FLUSHDB
```

---

## 🧪 Testing

### Run Test Suite

```bash
# Run all tests
docker compose exec backend pytest app/tests/ -v

# Run specific test file
docker compose exec backend pytest app/tests/test_user.py -v

# Run with coverage report
docker compose exec backend pytest app/tests/ --cov=app --cov-report=html

# Run tests with detailed output
docker compose exec backend pytest app/tests/ -vv -s

# Run specific test function
docker compose exec backend pytest app/tests/test_user.py::test_signup_invalid_email -v
```

### Test Structure

```
app/tests/
├── test_user.py                         # User authentication tests
│   ├── test_signup_invalid_email
│   ├── test_login_wrong_password
│   ├── test_login_success
│   ├── test_me_authenticated
│   ├── test_delete_me_unauthenticated
│   ├── test_admin_get_users_forbidden
│   └── test_create_user_with_rollback
│
├── test_company.py                      # Company CRUD tests
│   ├── test_search_companies
│   ├── test_get_my_company_unauthenticated
│   ├── test_create_company_unverified_email
│   ├── test_update_my_company_success
│   └── test_admin_delete_company
│
├── test_product.py                      # Product management tests
├── test_commune.py                      # Commune management tests
├── test_health.py                       # Health check tests
├── test_orphan_image_cleanup.py         # Image cleanup job test
└── test_refresh_materialized_view.py    # Materialized view test
```

### Test Features

- **Rollback support** (no test data pollution)
- **Fixtures** for app, database, and test users
- **Async test support** (pytest-asyncio)
- **Isolated test database** (no impact on dev data)
- **Mock authentication** (JWT token generation)

### Manual Testing

#### Test Email Verification
```bash
# 1. Sign up a new user via API
curl -X POST http://localhost/api/v1/users/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","email":"test@example.com","password":"TestPass123!"}'

# 2. Check backend logs for verification link
docker compose logs backend | grep "verification_email_sent"

# 3. Extract token and visit:
http://localhost/api/v1/users/verify-email/{token}
```

#### Test NSFW Detection
```bash
# Upload an image that triggers NSFW model
# (Model will reject if confidence > 0.75)
```

#### Test Rate Limiting
```bash
# Send 25 rapid requests (limit is 20/sec)
for i in {1..25}; do
  curl http://localhost/api/v1/products/ &
done

# Expected: Some requests receive 429 Too Many Requests
```

---

## 🚢 Deployment

### Production Checklist

#### Security
- [ ] **Remove CSRF admin bypass** from `backend/app/auth/csrf.py`
- [ ] **Remove admin bypass endpoints** (`/use-postman-or-similar-to-bypass-csrf`)
- [ ] **Change all default passwords** (PostgreSQL, MinIO, admin user)
- [ ] **Generate secure SECRET_KEY** (64+ characters): `openssl rand -hex 32`
- [ ] **Set DEBUG=false** in `.env`
- [ ] **Configure ALLOWED_ORIGINS** (no wildcards, explicit domains only)
- [ ] **Enable database SSL** (`sslmode=require`)
- [ ] **Set up HTTPS/TLS** with valid certificates (Let's Encrypt)
- [ ] **Configure firewall rules** (close unnecessary ports)
- [ ] **Review CORS configuration** (strict origin policy)
- [ ] **Set secure password policy** (min length, complexity)
- [ ] **Enable database backups** (automated daily)

#### Infrastructure
- [ ] **Set up domain name** and DNS records
- [ ] **Configure SSL certificates** (nginx + PostgreSQL)
- [ ] **Set up monitoring** (health checks, uptime monitoring)
- [ ] **Configure log aggregation** (ELK stack, Datadog, etc.)
- [ ] **Test email delivery** (Resend production API key)
- [ ] **Set up Redis persistence** (AOF or RDB)
- [ ] **Configure backup strategy** (PostgreSQL, MinIO)
- [ ] **Review rate limits** (adjust for production traffic)
- [ ] **Set up CDN** (for static assets and images)
- [ ] **Configure auto-scaling** (if using Kubernetes)

#### Environment Variables (Production)

```env
# Security
DEBUG=false
SECRET_KEY=<64-character-hex-string-from-openssl-rand>
ADMIN_API_KEY=  # REMOVE THIS LINE ENTIRELY

# Database (use managed PostgreSQL in production)
DATABASE_URL=postgresql+asyncpg://user:strong_password@db.example.com:5432/proveo?sslmode=require
POSTGRES_PASSWORD=<32-character-random-password>

# Redis (use managed Redis in production)
REDIS_URL=rediss://default:password@redis.example.com:6379/0

# MinIO (or use AWS S3)
MINIO_ROOT_USER=<random-username>
MINIO_ROOT_PASSWORD=<32-character-random-password>
MINIO_SECURE=true
MINIO_ENDPOINT=s3.yourdomain.com:9000

# Email
RESEND_API_KEY=<production-resend-api-key>
EMAIL_FROM=noreply@yourdomain.com
API_BASE_URL=https://yourdomain.com

# CORS
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Admin
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_BYPASS_IPS=  # REMOVE THIS LINE ENTIRELY
```

### Docker Production Build

```bash
# Build production images
docker compose -f docker-compose.prod.yml build

# Start services
docker compose -f docker-compose.prod.yml up -d

# Run migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# Create admin user
docker compose -f docker-compose.prod.yml exec backend python -m scripts.admin.create_admin
```

### Nginx Configuration (Production)

Add to `nginx/nginx.conf`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;
    
    # SSL certificates (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    # SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # HSTS (uncomment after testing SSL)
    # add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    
    # ... rest of nginx configuration
}
```

### Kubernetes Deployment (Future)

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: proveo-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: proveo-backend
  template:
    metadata:
      labels:
        app: proveo-backend
    spec:
      containers:
      - name: backend
        image: your-registry/proveo-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: proveo-secrets
              key: database-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
```

### Monitoring & Alerting

**Recommended tools:**
- **Uptime monitoring**: UptimeRobot, Pingdom
- **Application monitoring**: Datadog, New Relic
- **Log aggregation**: ELK Stack, Papertrail
- **Error tracking**: Sentry
- **Metrics**: Prometheus + Grafana

**Health check endpoints:**
```bash
# Nginx
curl http://yourdomain.com/health

# Backend
curl http://yourdomain.com/api/v1/health/

# Database
curl http://yourdomain.com/api/v1/health/database
```

### Backup & Disaster Recovery

```bash
# Automated daily backups (cron)
0 2 * * * docker compose exec postgres pg_dump -U postgres portfolio | gzip > /backups/portfolio-$(date +\%Y\%m\%d).sql.gz

# Restore from backup
gunzip < backup.sql.gz | docker compose exec -T postgres psql -U postgres portfolio

# Backup MinIO images
docker compose exec minio mc mirror /data/images /backups/minio/

# Backup environment variables (encrypted)
gpg -c .env
```

---

## 🗺️ Roadmap

### Phase 1: Core Features (Completed ✅)
- [x] User authentication with email verification
- [x] Company CRUD with image uploads
- [x] Product and commune management
- [x] Search with materialized views
- [x] Admin panel functionality
- [x] NSFW content detection
- [x] Rate limiting and caching

### Phase 2: Production Ready (In Progress 🚧)
- [ ] **Remove CSRF bypass logic**
- [ ] **SSL/TLS certificates** (Let's Encrypt)
- [ ] **CI/CD pipeline** (GitHub Actions)
  - Automated testing on PR
  - Docker image building
  - Deployment to staging/production
- [ ] **Monitoring dashboard** (Grafana + Prometheus)
- [ ] **Automated backups** (PostgreSQL + MinIO)
- [ ] **Error tracking** (Sentry integration)

### Phase 3: Scaling (Q2 2026)
- [ ] **Kubernetes deployment** (K3s/K8s)
  - Helm charts
  - Auto-scaling policies
  - Rolling updates
- [ ] **Database read replicas** (PostgreSQL streaming replication)
- [ ] **Redis Sentinel** (high availability)
- [ ] **CDN integration** (CloudFlare/Fastly)
- [ ] **Horizontal pod autoscaling**

### Phase 4: Advanced Features (Q3 2026)
- [ ] **Real-time notifications** (WebSocket support)
- [ ] **Advanced search** (Elasticsearch integration)
  - Fuzzy search improvements
  - Faceted search
  - Geo-location search
- [ ] **Payment integration** (Stripe/MercadoPago)
  - Subscription plans
  - Featured listings
- [ ] **Analytics dashboard** (user behavior tracking)
- [ ] **Multi-language support** (i18n beyond ES/EN)

### Phase 5: Enhancements (Q4 2026)
- [ ] **Mobile app** (React Native)
- [ ] **Company reviews/ratings**
- [ ] **Messaging system** (buyer-seller communication)
- [ ] **Advanced image gallery** (multiple images per company)
- [ ] **Email campaigns** (marketing automation)
- [ ] **API rate tier system** (free/paid API access)

---

## 🤝 Contributing

This is a portfolio project and is not actively accepting contributions. However, feedback and suggestions are welcome!

If you find a bug or security issue:
1. **Do not** open a public issue for security vulnerabilities
2. Email: your-acos2014600836@gmail.com
3. For non-security issues, open a GitHub issue with:
   - Steps to reproduce
   - Expected vs. actual behavior
   - Environment details (Docker version, OS, etc.)

---

## 📄 License

This project is for portfolio demonstration purposes only.

**No License** - All rights reserved. This code is provided for review and educational purposes. You may NOT:
- Use this code in commercial projects
- Distribute or sell this code
- Remove or modify copyright notices

You MAY:
- View the code for learning purposes
- Reference the code in technical discussions
- Use small snippets with proper attribution

For licensing inquiries, contact: acos2014600836@gmail.com

---

## 📞 Support

### Documentation
- **README**: This document
- **API Docs**: http://localhost/docs (when running)
- **Code Comments**: Inline documentation in source files

### Contact
- **Email**: your-acos2014600836@gmail.com
- **GitHub**: https://github.com/uwuolguin/portfolio-2025
- **LinkedIn**: https://www.linkedin.com/in/uwuolguin/

### Common Issues

**Issue**: Docker containers won't start
```bash
# Solution: Check for port conflicts
docker compose down
lsof -i :80 -i :5432 -i :6379 -i :9000
# Kill conflicting processes and restart
```

**Issue**: Database migrations fail
```bash
# Solution: Reset database and re-run migrations
docker compose down -v
docker compose up -d postgres
docker compose exec backend alembic upgrade head
```

**Issue**: NSFW model not loading
```bash
# Solution: Increase Docker memory limit to 8GB
# Docker Desktop -> Settings -> Resources -> Memory
```

**Issue**: Redis connection errors
```bash
# Solution: Redis is optional, app will continue
# Check logs: docker compose logs redis
# Restart: docker compose restart redis
```

**Issue**: Email verification not working
```bash
# Solution: Check Resend API key
docker compose logs backend | grep resend
# Verify RESEND_API_KEY in .env
```

---

## 🙏 Acknowledgments

### Technologies
- **FastAPI** - For the incredible async Python framework
- **PostgreSQL** - For robust, reliable data storage
- **Redis** - For blazing-fast caching
- **MinIO** - For S3-compatible object storage
- **OpenNSFW2** - For AI-powered content moderation
- **Resend** - For developer-friendly email delivery
- **Docker** - For containerization and portability

### Inspiration
- Real-world B2B marketplace platforms
- Modern API design best practices
- Production-ready architecture patterns

### Learning Resources
- FastAPI documentation
- PostgreSQL performance tuning guides
- OWASP security guidelines
- Docker best practices

---

**Built with ❤️ as a portfolio project**

**Last Updated**: January 2026

---

## 🎯 Project Goals

This project was built to demonstrate:

✅ **Full-stack development** - Backend API + Frontend + Database + Infrastructure  
✅ **Production-ready architecture** - Security, performance, monitoring  
✅ **Modern tech stack** - Async Python, PostgreSQL, Redis, Docker  
✅ **Best practices** - Testing, logging, documentation, CI/CD readiness  
✅ **Problem-solving** - Image processing, search optimization, rate limiting  
✅ **DevOps skills** - Containerization, orchestration, deployment strategies  

---

## ⚖️ Disclaimer

This is a **portfolio project** created for demonstration and learning purposes. While it implements production-grade patterns and security practices, it should be thoroughly reviewed and hardened before use in any real-world production environment.

**Key considerations before production use:**
- Security audit by professionals
- Load testing and performance optimization
- Compliance review (GDPR, privacy laws)
- Legal review (terms of service, privacy policy)
- Business logic validation
- Comprehensive integration testing
- Disaster recovery planning
- **Removal of CSRF admin bypass logic**

---
> ⚠️ **CRITICAL SECURITY WARNING FOR PRODUCTION DEPLOYMENT** ⚠️
> 
> **This codebase contains an admin CSRF bypass mechanism for development/testing purposes that MUST be removed before any production deployment.**
>
> **Location**: `backend/app/auth/csrf.py` - The `validate_csrf_token()` function contains logic that allows admin users to bypass CSRF protection using the `X-Admin-Bypass-CSRF` header with an API key.
>
> **Why this is dangerous**: This bypass mechanism could allow attackers to perform CSRF attacks against admin accounts if the API key is compromised or predictable.
>
> **Before production**:
> 1. Remove the entire admin bypass block from `validate_csrf_token()` in `backend/app/auth/csrf.py`
> 2. Remove all references to `ADMIN_BYPASS_IPS` and `admin_api_key` from configuration
> 3. Force all admin operations to use standard CSRF tokens via browser forms
> 4. Remove `/use-postman-or-similar-to-bypass-csrf` endpoints or protect them properly
>
> **This is a portfolio/demonstration project. The bypass exists solely to facilitate API testing with tools like Postman.**


**⭐ If you found this project helpful, please consider starring the repository!**
---