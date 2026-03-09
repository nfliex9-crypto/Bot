# ============================================================
# AI Trading Bot — Production Dockerfile
# Python 3.11-slim, non-root user, health-check included
# ============================================================
FROM python:3.11-slim

LABEL maintainer="AI Trading Bot"
LABEL description="Automated trading platform — FastAPI + PostgreSQL + Redis"

# ── System deps ───────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    curl \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ────────────────────────────────────────
WORKDIR /app

# ── Python dependencies (layer-cached) ───────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ── Application code ─────────────────────────────────────────
COPY app/        ./app/
COPY scripts/    ./scripts/
COPY alembic/    ./alembic/
COPY alembic.ini ./

# ── Runtime directories ───────────────────────────────────────
RUN mkdir -p /app/logs /app/models /app/data /app/app/core/ai/models

# ── Entrypoint script ─────────────────────────────────────────
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# ── Non-root user ────────────────────────────────────────────
RUN useradd -m -u 1000 trader && \
    chown -R trader:trader /app /app/logs /app/models /app/data && \
    chmod +x /docker-entrypoint.sh
USER trader

# ── Environment ──────────────────────────────────────────────
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_DIR=/app/logs

# ── Health check ─────────────────────────────────────────────
HEALTHCHECK --interval=15s --timeout=10s --start-period=45s --retries=5 \
    CMD curl -sf http://localhost:8000/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--loop", "asyncio", \
     "--log-config", "/dev/null"]
