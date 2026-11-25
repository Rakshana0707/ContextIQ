# ContextIQ Deployment, Security & Operations Guide (Phase 7.9)

This guide documents the production deployment, security hardening, secrets management, and disaster recovery architecture for **ContextIQ**, a privacy-conscious behavioral intelligence and micro-delay analytics platform.

---

## 1. Security Architecture & Invariants

ContextIQ is built with defense-in-depth principles across all platform layers:

1. **User Isolation & Object-Level Authorization (IDOR Prevention)**:
   - Every database query enforces strict tenant isolation (`user_id == current_user.id`).
   - Cross-user data access is structurally impossible at the API, service, and database RLS boundaries.
2. **Surveillance Protection & Privacy Invariant**:
   - The platform strictly forbids and actively blocks collection of keystrokes, screenshots, clipboard contents, private messages, and document bodies.
   - Client-side (`AgentPrivacyGuard`) and backend ingestion (`telemetry.py`) reject surveillance fields with HTTP 400.
3. **Encrypted Third-Party Credentials**:
   - OAuth access and refresh tokens for Google Calendar and Microsoft Outlook are encrypted at rest using AES-256-GCM binary ciphertext. Plaintext tokens are never stored or exposed to browser-side JavaScript.
4. **Governed Autonomous Workflows**:
   - Zero arbitrary code execution. Workflows execute only allowlisted, deterministic action catalog handlers with runtime policy checks, bounded retries, and emergency kill switches.
5. **Defense-in-Depth Network Hardening**:
   - Automated rate limiting (180 requests/min sliding window).
   - Strict 5MB request body size limits preventing memory exhaustion attacks.
   - Production security headers: HSTS, Content-Security-Policy, X-Frame-Options (`DENY`), X-Content-Type-Options (`nosniff`), Permissions-Policy.

---

## 2. Secrets Management & Configuration Checklist

All production configuration must flow through environment variables. **Never commit secrets to source control.**

| Variable | Description | Production Requirement |
| :--- | :--- | :--- |
| `APP_ENV` | Application environment (`production` / `staging` / `development`) | Must be set to `production` |
| `SECRET_KEY` | High-entropy JWT signing secret (minimum 32 bytes) | **Mandatory.** The backend halts on boot if the development default `dev-secret-change-me` is present. |
| `DATABASE_URL` | PostgreSQL connection string with credentials | Use TLS-enabled connection string (e.g. `postgresql+psycopg://...`) |
| `POSTGRES_PASSWORD` | PostgreSQL database password | High-entropy randomly generated secret |
| `CORS_ORIGINS` | Allowed frontend origin URLs | Restrict strictly to authorized domains (e.g. `["https://app.contextiq.io"]`) |
| `LLM_API_KEY` | Anthropic / OpenAI API key for intelligence workflows | Managed in container secrets or cloud secret manager |
| `GOOGLE_CLIENT_SECRET` | OAuth client secret for Google Calendar sync | Backend-only environment secret |
| `MICROSOFT_CLIENT_SECRET` | OAuth client secret for Microsoft 365 sync | Backend-only environment secret |

---

## 3. Local Development Setup

To run ContextIQ locally with Docker:

```bash
# 1. Clone repository and create local environment file
cp .env.example .env

# 2. Build and start local services (Postgres on 5433, Backend on 8000, Frontend on 3000)
docker compose up --build

# 3. Apply database migrations
docker compose exec backend alembic upgrade head

# 4. Verify system health
curl -fsS http://localhost:8000/health/ready
```

---

## 4. Production Deployment Orchestration

ContextIQ provides a hardened production stack in `docker-compose.prod.yml`:

```bash
# 1. Prepare production environment file (.env.production)
cp .env.example .env.production
chmod 600 .env.production

# Edit .env.production with genuine production credentials
nano .env.production

# 2. Build and start the production cluster
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# 3. Execute database migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 4. Verify cluster health via NGINX reverse proxy
curl -fsS https://api.contextiq.io/health/ready
```

### Production Security Protections Configured
- **Non-Root Execution**: Backend container runs as unprivileged user `contextiq:contextiq`. Frontend container runs as user `nextjs:nodejs`.
- **Privilege Escalation Blocked**: All services enforce `security_opt: [no-new-privileges:true]`.
- **Resource Constraints**: Hard limits set on memory (2GB backend, 1.5GB database) and CPU quotas (2.0 cores).

---

## 5. NGINX Reverse Proxy & TLS Configuration

The NGINX reverse proxy (`docker/nginx/nginx.conf`) handles:
- **TLS Termination**: Configured for TLSv1.2 and TLSv1.3 with modern secure ciphers.
- **Rate Limiting**: `api_zone` limits client IPs to 30 requests/second with burst buffer of 50.
- **Request Size Limiting**: `client_max_body_size 5M;`
- **Security Headers**: HSTS, CSP, X-Frame-Options, X-Content-Type-Options.

### TLS Certificate Provisioning (Let's Encrypt / Certbot)
```bash
# On production host
sudo certbot certonly --standalone -d app.contextiq.io -d api.contextiq.io

# Mount certificates into docker/nginx/certs:
# - /etc/letsencrypt/live/app.contextiq.io/fullchain.pem
# - /etc/letsencrypt/live/app.contextiq.io/privkey.pem
```

---

## 6. Disaster Recovery & Backup Runbook

Automated backup and integrity verification are managed by `scripts/backup_restore.py`.

### 1. Creating a Backup
```bash
# Back up production database to ./backups with SHA-256 integrity hash
python scripts/backup_restore.py backup \
  --db-url "$DATABASE_URL" \
  --out-dir /var/backups/contextiq
```

### 2. Verifying Backup Integrity
```bash
# Validates archive compression and matches cryptographic SHA-256 hash
python scripts/backup_restore.py verify \
  --file /var/backups/contextiq/contextiq_backup_20261125_220000Z.sql.gz
```

### 3. Restoring from a Backup
```bash
# Restores database after verifying cryptographic checksum
python scripts/backup_restore.py restore \
  --db-url "$DATABASE_URL" \
  --file /var/backups/contextiq/contextiq_backup_20261125_220000Z.sql.gz
```

---

## 7. Zero-Downtime Rolling Upgrade & Emergency Rollback

### Rolling Upgrade Procedure
1. Create pre-deployment database backup: `python scripts/backup_restore.py backup`.
2. Apply forward migrations: `docker compose -f docker-compose.prod.yml exec backend alembic upgrade head`.
3. Rebuild and restart application containers:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --no-deps --build backend frontend
   ```
4. Verify readiness probe: `curl -fsS http://localhost:8000/health/ready`.

### Emergency Rollback Runbook
If an upgrade causes service degradation:
1. **Engage Global Kill Switch**:
   ```bash
   curl -X POST http://localhost:8000/api/v1/safety/emergency-stop \
     -H "Authorization: Bearer <ADMIN_JWT>" \
     -H "Content-Type: application/json" \
     -d '{"scope": "ADMIN_GLOBAL", "reason": "Deployment regression rollback"}'
   ```
2. **Revert Application Containers**:
   ```bash
   git checkout <PREVIOUS_STABLE_COMMIT>
   docker compose -f docker-compose.prod.yml up -d --build
   ```
3. **Downgrade Database Schema** (if applicable):
   ```bash
   docker compose -f docker-compose.prod.yml exec backend alembic downgrade -1
   ```
4. **Lift Emergency Stop** when tests pass.

---

## 8. GDPR & Privacy Compliance Capabilities

- **Article 20 Right to Data Portability**: Users can download their complete profile, tasks, telemetry metadata, automation rules, and audit logs via `GET /api/v1/privacy/data/export`.
- **Article 17 Right to Erasure**: Complete account and data destruction via `POST /api/v1/privacy/account/delete` with confirmation phrase `"DELETE MY ENTIRE ACCOUNT"`.
- **Data Minimization**: Automatic redaction of file paths, URLs, query parameters, credit card numbers, and SSNs from window titles.
- **Granular Consent**: Immutable versioned consent records with instant revocation (`POST /api/v1/privacy/consent/revoke`).
