# AI Automated Trading System

End-to-end AI-assisted automated trading platform for:
- **Forex** (MetaTrader5 execution)
- **Crypto** (Binance execution)

## Stack

- **Backend**: Python, FastAPI, Pandas, NumPy, Scikit-learn
- **Database**: PostgreSQL (SQLAlchemy ORM)
- **Frontend**: Flutter mobile dashboard
- **Infra**: Docker + Docker Compose (cloud-ready baseline)

## Core Features

- Strategy engine:
  - Liquidity sweep detection
  - Break of Structure (BOS)
  - Pullback entry model
- Risk engine:
  - 0.75% risk per trade
  - 15% max drawdown guard
  - 3 trades per session limit
  - ATR-based stop loss
  - TP1 / TP2 / TP3
  - Move stop to break-even after TP1
- AI layer:
  - Random Forest classifier
  - Trade confidence scoring
- Execution:
  - MT5 adapter
  - Binance adapter
  - Paper fallback mode when credentials are unavailable
- Dashboard APIs:
  - Equity
  - Trade history
  - AI confidence
  - Live signals

---

## Repository Structure

```text
backend/
  app/
    api/
    core/
    models/
    repositories/
    schemas/
    services/
  tests/
frontend/
  lib/
docker-compose.yml
```

## Quick Start (Docker)

1. Copy environment file:
   ```bash
   cp .env.example .env
   ```
2. Start services:
   ```bash
   docker compose up --build
   ```
3. Backend:
   - API docs: `http://localhost:8000/docs`
4. Frontend (Flutter Web build served via Nginx):
   - `http://localhost:8080`

## API Endpoints

- `GET /health`
- `POST /signals/run-once` (run strategy + AI + risk + execution pipeline once)
- `GET /signals/live`
- `GET /trades/history`
- `POST /trades/{trade_id}/tp1-hit` (moves stop loss to break-even)
- `GET /dashboard/equity`

## Backend Local Dev

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

## Frontend Local Dev

```bash
cd frontend
flutter pub get
flutter run
```

## Notes

- Live broker execution requires valid MT5/Binance credentials and network access.
- `MetaTrader5` Python package is optional and platform-dependent; MT5 execution adapter falls back to paper mode when unavailable.
- In absence of credentials, the system runs in safe paper mode for development.
- This project is a technical framework, not financial advice.
