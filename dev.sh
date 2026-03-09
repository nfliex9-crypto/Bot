#!/usr/bin/env bash
# ============================================================
# dev.sh — Local development server (no Docker required)
#
# Usage:  ./dev.sh
#         ./dev.sh --port 8080
#         ./dev.sh --no-reload
#
# Requires: Python 3.10+, dependencies installed (pip install -r requirements.txt)
# The bot will run in PAPER mode with a local SQLite fallback
# if PostgreSQL is not available.
# ============================================================
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[dev]${NC} $*"; }
success() { echo -e "${GREEN}[dev]${NC} $*"; }
warn()    { echo -e "${YELLOW}[dev]${NC} $*"; }
error()   { echo -e "${RED}[dev]${NC} $*" >&2; exit 1; }

# ── Defaults ──────────────────────────────────────────────────
PORT=8000
RELOAD="--reload"
HOST="0.0.0.0"

for arg in "$@"; do
    case $arg in
        --port=*)  PORT="${arg#*=}" ;;
        --port)    shift; PORT="$1" ;;
        --no-reload) RELOAD="" ;;
        --host=*)  HOST="${arg#*=}" ;;
        --help|-h)
            echo "Usage: $0 [--port PORT] [--no-reload] [--host HOST]"
            exit 0
            ;;
    esac
done

# ── Python check ──────────────────────────────────────────────
PYTHON=$(command -v python3 || command -v python || true)
[ -z "$PYTHON" ] && error "Python 3 not found"

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Python $PY_VERSION at $PYTHON"

# ── Environment ───────────────────────────────────────────────
if [ ! -f ".env" ]; then
    warn ".env not found — copying from .env.example"
    cp .env.example .env
fi

# Override DB/Redis to localhost for direct dev usage
export PYTHONPATH="${PYTHONPATH:-$(pwd)}"
export BOT_AUTO_START="${BOT_AUTO_START:-true}"
export TRADING_MODE="${TRADING_MODE:-paper}"
export LOG_DIR="${LOG_DIR:-./logs}"

# Point to localhost services if running outside Docker
if [ "${DATABASE_URL:-}" = "" ] || echo "${DATABASE_URL}" | grep -q "@postgres:"; then
    export DATABASE_URL="postgresql://trader:trading_password@localhost:5432/trading_bot"
    warn "DATABASE_URL set to localhost PostgreSQL — start postgres first if needed"
fi

if [ "${REDIS_URL:-}" = "" ] || echo "${REDIS_URL}" | grep -q "@redis:"; then
    export REDIS_URL="redis://localhost:6379/0"
fi

mkdir -p logs models data

# ── Dependencies check ────────────────────────────────────────
info "Checking dependencies..."
$PYTHON -c "import fastapi, uvicorn, sqlalchemy, pandas, sklearn, loguru" 2>/dev/null || {
    warn "Some dependencies missing — installing..."
    $PYTHON -m pip install -q -r requirements.txt
}
success "Dependencies OK"

# ── AI model bootstrap ────────────────────────────────────────
MODEL_PATH="${MODEL_PATH:-./models/rf_classifier.pkl}"
if [ ! -f "$MODEL_PATH" ]; then
    info "No model found — bootstrapping with synthetic data..."
    $PYTHON scripts/train_model.py \
        --synthetic \
        --n-synthetic 500 \
        --model-path "$MODEL_PATH" 2>/dev/null || warn "Model bootstrap failed — using rule-based scoring"
fi

# ── Start uvicorn ─────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}Starting development server...${NC}"
echo ""
echo -e "  ${BOLD}API     →  http://localhost:${PORT}${NC}"
echo -e "  ${BOLD}Docs    →  http://localhost:${PORT}/docs${NC}"
echo -e "  ${BOLD}Health  →  http://localhost:${PORT}/health${NC}"
echo -e "  ${BOLD}Mode    :  ${TRADING_MODE}${NC}"
echo ""
info "Press Ctrl+C to stop"
echo ""

exec $PYTHON -m uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    $RELOAD \
    --loop asyncio \
    --log-level info \
    --use-colors
