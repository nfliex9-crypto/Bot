#!/usr/bin/env bash
# ============================================================
# Docker Entrypoint — AI Trading Bot
#
# 1. Wait for PostgreSQL to be ready
# 2. Run Alembic migrations
# 3. Optionally bootstrap the AI model
# 4. Start the application
# ============================================================
set -euo pipefail

DB_HOST="${DB_HOST:-postgres}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-trader}"
DB_NAME="${DB_NAME:-trading_bot}"
MAX_RETRIES=30
RETRY_INTERVAL=2

log() { echo "[entrypoint] $(date -u '+%Y-%m-%dT%H:%M:%SZ') $*"; }

# ── 1. Wait for PostgreSQL ────────────────────────────────────
log "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."
for i in $(seq 1 $MAX_RETRIES); do
    if nc -z -w 2 "$DB_HOST" "$DB_PORT" 2>/dev/null; then
        log "PostgreSQL is reachable (attempt $i)"
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        log "ERROR: PostgreSQL not reachable after ${MAX_RETRIES} attempts — aborting"
        exit 1
    fi
    log "  waiting... attempt $i/${MAX_RETRIES}"
    sleep $RETRY_INTERVAL
done

# Extra 2-second grace period for PG to finish initialization
sleep 2

# ── 2. Run Alembic Migrations ────────────────────────────────
log "Running database migrations..."
cd /app
if alembic upgrade head 2>&1; then
    log "Migrations complete"
else
    log "WARNING: migrations failed (tables may already exist — continuing)"
fi

# ── 3. Bootstrap AI model (if missing) ───────────────────────
MODEL_PATH="${MODEL_PATH:-/app/models/rf_classifier.pkl}"
if [ ! -f "$MODEL_PATH" ]; then
    log "No model found at ${MODEL_PATH} — bootstrapping with synthetic data..."
    python3 scripts/train_model.py \
        --synthetic \
        --n-synthetic 1000 \
        --model-path "$MODEL_PATH" 2>&1 || \
        log "WARNING: model bootstrap failed — bot will use rule-based scoring"
    log "Model bootstrap complete"
fi

# ── 4. Start application ──────────────────────────────────────
log "Starting application: $*"
exec "$@"
