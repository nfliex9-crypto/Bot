#!/usr/bin/env bash
# ============================================================
# start.sh — One-command production startup
#
# Usage:  ./start.sh
#         ./start.sh --monitoring          (includes Grafana + Prometheus)
#         ./start.sh --no-build            (skip image rebuild)
#         ./start.sh --detach              (run in background)
#
# Requires: Docker + Docker Compose v2
# ============================================================
set -euo pipefail

# ── Colours ───────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }
header()  { echo -e "\n${BOLD}${CYAN}$*${NC}"; }

# ── Parse arguments ───────────────────────────────────────────
BUILD_FLAG="--build"
DETACH_FLAG=""
PROFILES=""

for arg in "$@"; do
    case $arg in
        --no-build)   BUILD_FLAG="" ;;
        --detach|-d)  DETACH_FLAG="--detach" ;;
        --monitoring) PROFILES="--profile monitoring" ;;
        --help|-h)
            echo "Usage: $0 [--no-build] [--detach] [--monitoring]"
            exit 0
            ;;
    esac
done

# ── Header ────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║        AI TRADING BOT — STARTUP              ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════╝${NC}"
echo ""

# ── Check prerequisites ───────────────────────────────────────
header "Checking prerequisites..."

command -v docker  >/dev/null 2>&1 || error "Docker is not installed"
command -v docker  >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || \
    command -v docker-compose >/dev/null 2>&1 || error "Docker Compose is not installed"

# Choose docker compose vs docker-compose
if docker compose version >/dev/null 2>&1; then
    DC="docker compose"
else
    DC="docker-compose"
fi

success "Docker found: $(docker --version)"
success "Compose found: $($DC version)"

# ── Environment file ──────────────────────────────────────────
header "Checking environment..."

if [ ! -f ".env" ]; then
    warn ".env not found — copying from .env.example"
    cp .env.example .env
    success "Created .env from .env.example"
else
    success ".env exists"
fi

# Ensure SECRET_KEY is not the placeholder
if grep -q "your-secret-key-here\|dev-secret-key" .env 2>/dev/null; then
    warn "SECRET_KEY is using a default value — safe for local dev only"
fi

# ── Stop any previous stack ───────────────────────────────────
header "Cleaning up previous containers..."
$DC down --remove-orphans 2>/dev/null || true
success "Previous containers removed"

# ── Build & Start ─────────────────────────────────────────────
header "Building and starting services..."
info "Services: api, postgres, redis${PROFILES:+ + monitoring stack}"

$DC $PROFILES up $BUILD_FLAG $DETACH_FLAG

# ── Post-startup checks (only in foreground / after detach) ───
if [ -n "$DETACH_FLAG" ]; then
    info "Waiting for API to become healthy..."
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
            echo ""
            success "API is healthy!"
            break
        fi
        printf "."
        sleep 2
    done
    echo ""

    # ── Final status ──────────────────────────────────────────
    echo ""
    echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${GREEN}║   SYSTEM RUNNING                             ║${NC}"
    echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${GREEN}║   API     →  http://localhost:8000           ║${NC}"
    echo -e "${BOLD}${GREEN}║   Docs    →  http://localhost:8000/docs      ║${NC}"
    echo -e "${BOLD}${GREEN}║   Health  →  http://localhost:8000/health    ║${NC}"
    echo -e "${BOLD}${GREEN}║   Status  →  http://localhost:8000/status    ║${NC}"
    if [ -n "$PROFILES" ]; then
    echo -e "${BOLD}${GREEN}║   Grafana →  http://localhost:3001           ║${NC}"
    echo -e "${BOLD}${GREEN}║   Metrics →  http://localhost:9090           ║${NC}"
    fi
    echo -e "${BOLD}${GREEN}╠══════════════════════════════════════════════╣${NC}"
    echo -e "${BOLD}${GREEN}║   Logs    :  docker compose logs -f api      ║${NC}"
    echo -e "${BOLD}${GREEN}║   Stop    :  docker compose down             ║${NC}"
    echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════╝${NC}"
    echo ""

    # Quick container health summary
    echo -e "${BOLD}Container status:${NC}"
    $DC ps
fi
