# 🚀 Proveo - B2B Provider Marketplace Platform

A full-stack marketplace platform connecting businesses with service providers in Chile. Built with modern technologies focusing on scalability, security, and performance.

---

## 📋 Table of Contents

- [✨ Features](#-features)
- [🏗️ Architecture](#-architecture)
- [🛠️ Tech Stack](#-tech-stack)
- [🚀 Getting Started](#-getting-started)
- [📚 API Documentation](#-api-documentation)
- [📁 Project Structure](#-project-structure)
- [🔒 Security Features](#-security-features)
- [⚡ Performance Optimizations](#-performance-optimizations)
- [💻 Development](#-development)
- [🚢 Deployment](#-deployment)
- [🗺️ Roadmap](#-roadmap)
- [📄 License](#-license)
- [👤 Author](#-author)
- [🙏 Acknowledgments](#-acknowledgments)
- [📞 Support](#-support)

---

## ✨ Features

### User Management
- **Email verification system** with automated emails (Resend API)
- **Role-Based Access Control (RBAC)** - Admin and User roles
- **JWT-based authentication** with secure HTTP-only cookies
- **CSRF protection** for all state-changing operations
- **Account self-deletion** with cascading cleanup

### Company Management
- **One company per user** business rule enforcement
- **Bilingual support** (Spanish/English) with automatic translation fallback
- **Image upload** with NSFW content detection (OpenNSFW2)
- **Full CRUD operations** with soft deletes
- **Admin company management** with audit logging

### Search & Discovery
- **Hybrid search system**:
  - Full-text search (PostgreSQL tsvector)
  - Trigram similarity matching (pg_trgm)
  - Materialized views for performance
- **Multi-filter search** (location, product type, keywords)
- **Pagination support**
- **Automatic index refresh**

### Infrastructure
- **Database connection pooling** with health monitoring
- **Redis caching** with graceful degradation
- **Rate limiting** (per-IP and global)
- **Structured logging** (JSON format with correlation IDs)
- **Docker containerization** with multi-stage builds

---

## 🏗️ Architecture

```
┌─────────────┐
│   Nginx     │ ← Reverse Proxy + Static Files
│   (Port 80) │
└──────┬──────┘
       │
       ├──────────────────┐
       │                  │
┌──────▼──────┐    ┌──────▼──────┐
│   FastAPI   │    │  Frontend   │
│  Backend    │    │   (Vanilla  │
│  (Port 8000)│    │   JS/HTML)  │
└──────┬──────┘    └─────────────┘
       │
       ├─────────────────┬───────────────┐
       │                 │               │
┌──────▼──────┐   ┌──────▼──────┐ ┌─────▼──────┐
│ PostgreSQL  │   │    Redis    │ │   Shared   │
│   Primary   │   │   Cache +   │ │   Volume   │
│  (Port 5432)│   │ Rate Limit  │ │  (Images)  │
└─────────────┘   └─────────────┘ └────────────┘
```

### Data Flow

1. **User Request** → Nginx (rate limit check)
2. **Nginx** → Backend (if API) or Static Files (if frontend)
3. **Backend**:
   - Validates JWT + CSRF tokens
   - Checks Redis cache
   - Queries PostgreSQL (with connection pooling)
   - Processes business logic
   - Returns response with correlation ID
4. **Frontend**: Dynamic rendering with localStorage state management

---

## 🛠️ Tech Stack

### Backend
- **FastAPI** - Modern async Python web framework
- **asyncpg** - Async PostgreSQL driver with connection pooling
- **Alembic** - Database migrations
- **Pydantic v2** - Data validation and settings management
- **Jose** - JWT token handling
- **bcrypt** - Password hashing
- **structlog** - Structured logging
- **tenacity** - Retry logic with exponential backoff

### Database
- **PostgreSQL 15** with extensions:
  - `pg_trgm` - Trigram similarity search
  - `uuid-ossp` - UUID generation
  - Full-text search (tsvector)
  - Materialized views for search performance

### Caching & Rate Limiting
- **Redis 7** - In-memory data store
- Graceful degradation (app continues if Redis unavailable)

### Frontend
- **Vanilla JavaScript** (ES6 modules)
- **Component-based architecture**
- **LocalStorage** for client state
- **Responsive CSS** (mobile-first)

### Image Processing
- **Pillow** - Image validation and optimization
- **OpenNSFW2** - AI-powered NSFW content detection

### DevOps
- **Docker Compose** - Multi-container orchestration
- **Nginx** - Reverse proxy and static file serving
- **Git** - Version control

---

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- Git
- 4GB RAM minimum
- Internet connection (for model downloads)

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/proveo.git
cd proveo
```

2. **Create environment file**
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=portfolio

# JWT Secret (generate with: openssl rand -hex 32)
SECRET_KEY=your_jwt_secret_key_here

# Email (get free API key from resend.com)
RESEND_API_KEY=re_your_api_key
ADMIN_EMAIL=admin@yourdomain.com
EMAIL_FROM=noreply@yourdomain.com

# API Base URL
API_BASE_URL=http://localhost
```

3. **Start the application**
```bash
docker-compose up -d
```

4. **Initialize the database**
```bash
# Run migrations
docker-compose exec backend alembic upgrade head

# Create test data (16 users + companies + 1 admin)
docker-compose exec backend python -m app.services.testing_setup_users_data

# Admin credentials: admin_test@mail.com / password
```

5. **Access the application**
- Frontend: http://localhost
- API Docs: http://localhost/docs
- Admin Dashboard: http://localhost/docs (use admin credentials)

### Test Users

After initialization, you'll have:
- **16 test users**: `testuser01@proveo.com` to `testuser16@proveo.com`
- **Password**: `TestPass123!` (all users)
- **1 admin**: `admin_test@mail.com` / `password`

---

## 📚 API Documentation

### Interactive Docs
- **Swagger UI**: http://localhost/docs
- **ReDoc**: http://localhost/redoc

### Key Endpoints

#### Authentication
```http
POST /api/v1/users/signup          # Create account (sends verification email)
POST /api/v1/users/login           # Login (returns JWT cookie + CSRF token)
POST /api/v1/users/logout          # Logout
GET  /api/v1/users/me              # Get current user
DELETE /api/v1/users/me            # Delete account (cascades to company)
```

#### Companies (Public)
```http
GET  /api/v1/companies/search      # Search companies (filters: q, commune, product)
```

#### Companies (Authenticated)
```http
POST /api/v1/companies/            # Create company (multipart/form-data)
GET  /api/v1/companies/user/my-company  # Get my company
PUT  /api/v1/companies/{uuid}      # Update company
DELETE /api/v1/companies/{uuid}    # Delete company
```

#### Admin Only
```http
GET    /api/v1/users/admin/all-users
DELETE /api/v1/users/admin/users/{uuid}
GET    /api/v1/companies/admin/all-companies
DELETE /api/v1/companies/admin/companies/{uuid}
POST   /api/v1/products/
PUT    /api/v1/products/{uuid}
DELETE /api/v1/products/{uuid}
POST   /api/v1/communes/
PUT    /api/v1/communes/{uuid}
DELETE /api/v1/communes/{uuid}
```

### Authentication Flow

1. **Signup**: User creates account → Email sent → User verifies email
2. **Login**: Returns JWT in HTTP-only cookie + CSRF token in response
3. **Authenticated Requests**: 
   - Include credentials (cookies sent automatically)
   - Add `X-CSRF-Token` header for POST/PUT/DELETE
4. **Logout**: Clears cookies

Example authenticated request:
```javascript
fetch('/api/v1/companies/', {
  method: 'POST',
  credentials: 'include',  // Send cookies
  headers: {
    'X-CSRF-Token': localStorage.getItem('csrf_token'),
    'Content-Type': 'application/json'
  },
  body: JSON.stringify(data)
})
```

---

## 📁 Project Structure

```
proveo/
├── backend/
│   ├── alembic/                 # Database migrations
│   │   └── versions/            # Migration files
│   ├── app/
│   │   ├── auth/                # Authentication & authorization
│   │   │   ├── csrf.py          # CSRF token handling
│   │   │   ├── jwt.py           # JWT operations
│   │   │   └── dependencies.py  # Auth dependencies
│   │   ├── database/
│   │   │   ├── connection.py    # Pool management
│   │   │   └── transactions.py  # DB operations (transactional)
│   │   ├── middleware/          # Custom middleware
│   │   │   ├── cors.py          # CORS configuration
│   │   │   ├── logging.py       # Request/response logging
│   │   │   └── security.py      # Security headers
│   │   ├── redis/               # Caching & rate limiting
│   │   │   ├── redis_client.py  # Redis connection manager
│   │   │   ├── cache_manager.py # Cache invalidation
│   │   │   ├── decorators.py    # @cache_response
│   │   │   └── rate_limit.py    # Rate limiting logic
│   │   ├── routers/             # API endpoints
│   │   │   ├── users.py         # User management
│   │   │   ├── companies.py     # Company CRUD
│   │   │   ├── products.py      # Product management
│   │   │   ├── communes.py      # Location management
│   │   │   └── health.py        # Health checks
│   │   ├── schemas/             # Pydantic models
│   │   │   ├── models.py        # SQLAlchemy models
│   │   │   ├── users.py         # User schemas
│   │   │   ├── companies.py     # Company schemas
│   │   │   ├── products.py      # Product schemas
│   │   │   └── communes.py      # Commune schemas
│   │   ├── services/            # Business logic
│   │   │   ├── email.py         # Email sending (Resend)
│   │   │   ├── create_admin.py  # Admin creation script
│   │   │   └── testing_setup_users_data.py  # Test data
│   │   ├── templates/           # Email templates
│   │   │   └── email_verification.py
│   │   ├── utils/               # Utilities
│   │   │   ├── db_retry.py      # Retry logic
│   │   │   ├── file_handler.py  # Image upload/NSFW detection
│   │   │   └── translator.py    # Auto-translation
│   │   ├── jobs/                # Background jobs
│   │   │   └── cleanup_orphan_images.py
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   └── main.py              # FastAPI app entry point
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── web-pages/
│       ├── 0-shared-components/
│       │   ├── header-nav-bar/  # Navigation
│       │   ├── footer/          # Footer
│       │   └── utils/
│       │       └── shared-functions.js  # Auth, API helpers
│       ├── front-page/          # Home + search
│       ├── sign-up/             # Registration
│       ├── log-in/              # Login
│       ├── publish/             # Create company
│       ├── profile-view/        # View profile
│       └── profile-edit/        # Edit company
├── nginx/
│   ├── nginx.conf               # Reverse proxy config
│   └── Dockerfile
├── files/                       # Shared volume
│   ├── pictures/                # User-uploaded images
│   └── logos/                   # Static assets
├── docker-compose.yml
├── init_backend.sh              # Initialization script
└── README.md
```

---

## 🔒 Security Features

### Authentication & Authorization
- **JWT tokens** in HTTP-only cookies (XSS protection)
- **CSRF tokens** for state-changing operations
- **bcrypt** password hashing (12 rounds)
- **Email verification** required before full access
- **Role-Based Access Control** (User/Admin)

### Input Validation
- **Pydantic v2** for request validation
- **File type validation** (JPEG/PNG only)
- **File size limits** (10MB max)
- **NSFW content detection** (AI-powered)
- **SQL injection prevention** (parameterized queries)

### Infrastructure Security
- **Security headers** (CSP, HSTS, X-Frame-Options, etc.)
- **Rate limiting** (per-IP and global)
- **CORS configuration** (explicit origin whitelist)
- **Database SSL** support
- **Secrets management** (environment variables)

### Audit & Monitoring
- **Structured logging** with correlation IDs
- **Failed login tracking**
- **Suspicious request detection**
- **Admin action logging**
- **Soft deletes** (audit trail preservation)

---

## ⚡ Performance Optimizations

### Database
- **Connection pooling** (5-20 connections)
- **Materialized views** for search (pg_trgm + tsvector)
- **Indexes** on frequently queried columns
- **Query timeout** enforcement (60s)
- **Retry logic** with exponential backoff

### Caching
- **Redis caching** for:
  - Product list (3 days TTL)
  - Commune list (3 days TTL)
  - Rate limit counters (1 min TTL)
- **Graceful degradation** (continues without cache)

### Frontend
- **Component lazy loading**
- **Image optimization** (auto-resize, JPEG quality: 90%)
- **Static asset caching** (30 days)
- **localStorage** for client state

### API
- **Async operations** (asyncpg, httpx)
- **Pagination** (default 20 items)
- **Concurrent refresh** for materialized views
- **Correlation IDs** for request tracing

---

## 💻 Development

### Local Development (Without Docker)

1. **Backend**
```bash
cd backend
python -m venv fastapi-env
source fastapi-env/bin/activate  # Windows: fastapi-env\Scripts\activate
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db"
export REDIS_URL="redis://localhost:6379/0"

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. **Frontend**
```bash
# Serve with any static server, e.g.:
python -m http.server 3000 --directory frontend/web-pages
```

### Running Tests

```bash
docker-compose exec backend pytest app/tests/ -v
```

### Database Migrations

```bash
# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Rollback last migration
docker-compose exec backend alembic downgrade -1
```

### Cleanup Orphan Images

```bash
# Dry run (shows what would be deleted)
docker-compose exec backend python -m app.jobs.cleanup_orphan_images

# Actually delete
docker-compose exec backend python -m app.jobs.cleanup_orphan_images --execute
```

### Create Admin User

```bash
docker-compose exec backend python -m app.services.create_admin
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# With timestamps
docker-compose logs -f --timestamps backend
```

---

## 🚢 Deployment

### Production Checklist

- [ ] Change all default passwords
- [ ] Generate secure `SECRET_KEY` (32+ bytes)
- [ ] Set `DEBUG=false`
- [ ] Configure `ALLOWED_ORIGINS` (no wildcards)
- [ ] Set up SSL/TLS certificates
- [ ] Configure backup strategy
- [ ] Set up monitoring (health checks)
- [ ] Configure log aggregation
- [ ] Test email delivery (Resend production API key)
- [ ] Review rate limits
- [ ] Set up domain name
- [ ] Configure firewall rules

### Docker Production Build

```bash
# Build images
docker-compose build

# Start in production mode
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Environment Variables (Production)

```env
# Security
DEBUG=false
SECRET_KEY=<64-char-hex-string>
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# Database (consider managed PostgreSQL)
DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/db?sslmode=require
POSTGRES_PASSWORD=<strong-password>

# Redis (consider managed Redis)
REDIS_URL=redis://redis-host:6379/0?ssl=true

# Email
RESEND_API_KEY=<production-api-key>
EMAIL_FROM=noreply@yourdomain.com
API_BASE_URL=https://yourdomain.com

# Admin
ADMIN_EMAIL=admin@yourdomain.com
```

### Nginx Configuration (Production)

Add SSL and domain:
```nginx
server {
    listen 443 ssl http2;
    server_name yourdomain.com;
    
    ssl_certificate /etc/ssl/certs/cert.pem;
    ssl_certificate_key /etc/ssl/private/key.pem;
    
    # ... rest of config
}
```

## 🗺️ Roadmap

- [ ] **K3s Deployment** - Kubernetes orchestration with DB replicas
- [ ] **Read Replicas** - Separate read/write database connections
- [ ] **Horizontal Scaling** - Auto-scaling backend pods
- [ ] **CI/CD Pipeline** - GitHub Actions for automated testing/deployment
- [ ] **Monitoring Dashboard** - Grafana + Prometheus
- [ ] **Real-time Notifications** - WebSocket support
- [ ] **Advanced Search** - Elasticsearch integration
- [ ] **Payment Integration** - Stripe/MercadoPago

---

## 📄 License

This project is for portfolio demonstration purposes.

---

## 👤 Author

**Your Name**
- Portfolio: [your-portfolio.com](https://your-portfolio.com)
- LinkedIn: [linkedin.com/in/yourprofile](https://linkedin.com/in/yourprofile)
- GitHub: [@yourusername](https://github.com/yourusername)

---

## 🙏 Acknowledgments

- FastAPI for the excellent framework
- PostgreSQL for robust data storage
- OpenNSFW2 for content moderation
- Resend for email delivery
- The open-source community

---

## 📞 Support

For questions or issues:
- Open an issue on GitHub
- Email: your.email@example.com

**Note**: This is a portfolio project. For production use, additional security hardening and testing is recommended.