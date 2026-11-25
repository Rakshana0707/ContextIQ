# ContextIQ Production Deployment Guide
## Architecture, Containerization, and Multi-Stage Rollout

This guide describes how to deploy ContextIQ in a secure, production-grade cloud environment using Docker Compose, NGINX TLS termination, PostgreSQL, and background worker orchestration.

---

## 1. Prerequisites & Environment Architecture

### Recommended Hardware Requirements
- **API Server & Worker**: 4 vCPU, 8 GB RAM, 50 GB SSD
- **PostgreSQL Database**: 2 vCPU, 4 GB RAM, 100 GB NVMe (with automated daily snapshots)
- **Network**: Inbound port 443 (HTTPS) and 80 (HTTP redirect); internal port 8000 (FastAPI), 5432 (Postgres).

### Environment Variables
Create a protected `.env.production` file on your target server:
```ini
# Environment
ENVIRONMENT=production
DEBUG=false
APP_NAME=ContextIQ
API_V1_PREFIX=/api/v1

# Security & Crypto
SECRET_KEY=generate-strong-64-char-random-key-here
ENCRYPTION_KEY=generate-base64-32-byte-aes-gcm-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Database
DATABASE_URL=postgresql://contextiq_user:secure_db_pass@postgres:5432/contextiq_prod

# Observability
LOG_LEVEL=INFO
LOG_FORMAT=json
ENABLE_PROMETHEUS_METRICS=true

# External OAuth Integrations
GOOGLE_CLIENT_ID=your-google-oauth-client-id
GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
MICROSOFT_CLIENT_ID=your-azure-ad-client-id
MICROSOFT_CLIENT_SECRET=your-azure-ad-client-secret
```

---

## 2. Docker Compose Production Topology

Deploy using the multi-container configuration:

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: contextiq_user
      POSTGRES_PASSWORD: secure_db_pass
      POSTGRES_DB: contextiq_prod
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U contextiq_user -d contextiq_prod"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    env_file: .env.production
    expose:
      - "8000"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health/live"]
      interval: 15s
      timeout: 5s
      retries: 3

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    expose:
      - "80"

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/certs:/etc/nginx/certs:ro
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
```

---

## 3. Step-by-Step Deployment Procedure

### Step 1: Clone Repository & Configure Secrets
```bash
git clone https://github.com/contextiq/contextiq.git /opt/contextiq
cd /opt/contextiq
chmod 600 .env.production
```

### Step 2: Run Alembic Database Migrations
```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

### Step 3: Launch Production Containers
```bash
docker compose -f docker-compose.prod.yml up -d
```

### Step 4: Verify System Readiness Probes
```bash
# 1. Liveness check
curl -f https://contextiq.yourdomain.com/api/v1/health/live

# 2. Readiness check (verifies database connectivity and worker queues)
curl -f https://contextiq.yourdomain.com/api/v1/health/ready
```

---

## 4. Zero-Downtime Rolling Update Strategy

When rolling out updates:
```bash
# 1. Pull latest images or rebuild
docker compose -f docker-compose.prod.yml build backend frontend

# 2. Run migrations (always backward-compatible)
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# 3. Graceful container restart
docker compose -f docker-compose.prod.yml up -d --no-deps --build backend frontend
```
