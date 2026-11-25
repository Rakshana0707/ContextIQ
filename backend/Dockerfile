# ContextIQ Backend — Production Dockerfile
FROM python:3.12-slim

WORKDIR /app

# psycopg needs libpq; curl/wget needed for healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Security hardening: Create dedicated non-root application user
RUN adduser --disabled-password --gecos "" --home /app --no-create-home contextiq && \
    chown -R contextiq:contextiq /app

USER contextiq

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
