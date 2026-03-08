# AI Automated Trading System

Cloud-ready monorepo for an AI-assisted automated trading platform covering:

- **Backend**: FastAPI, Pandas, NumPy, Scikit-learn
- **Markets**: Forex via MetaTrader5, Crypto via Binance
- **Risk engine**: 0.75% risk per trade, 15% max drawdown, 3 trades per session, ATR-based stop loss, TP1/TP2/TP3, break-even after TP1
- **AI layer**: Random Forest confidence scoring with heuristic fallback
- **Database**: PostgreSQL
- **Frontend**: Flutter dashboard for equity, trade history, live signals, and AI confidence
- **Deployment**: Docker Compose with backend, PostgreSQL, and Flutter web dashboard

## Repository layout

```text
backend/
  app/
    core/        configuration and logging
    db/          SQLAlchemy models and sessions
    routers/     FastAPI endpoints
    services/    strategy, AI, risk, execution, orchestration
  tests/         strategy and risk unit tests
frontend/
  lib/           Flutter dashboard UI
docker-compose.yml
.env.example
```

## Backend design

### Strategy logic

The trading engine runs a smart-money-inspired model:

1. **Liquidity sweep detection**: identifies stop hunts above/below recent swing levels
2. **Break of structure (BOS)**: confirms directional continuation after the sweep
3. **Pullback entry model**: validates continuation bias before sending the setup to the AI scorer

### AI confidence

- Pulls historical signal/trade pairs from PostgreSQL
- Trains a **Random Forest classifier** when enough closed/open samples exist
- Falls back to a rules-based confidence heuristic until the dataset is large enough

### Risk engine

- Risks **0.75%** of equity per trade
- Rejects new setups after **15% drawdown**
- Caps trading at **3 trades per session**
- Uses ATR-derived stop placement and three take-profit levels
- Arms **break-even** after TP1 is reached

### Execution

- **Paper trading** is enabled by default
- MetaTrader5 and Binance execution adapters are implemented with safe simulation fallback
- Broker-specific dependencies are isolated in `backend/requirements-brokers.txt`

## API endpoints

- `GET /health`
- `GET /api/dashboard/overview`
- `GET /api/dashboard/equity`
- `GET /api/signals/live`
- `POST /api/signals/run-cycle`
- `GET /api/trades/history`

## Local backend run

```bash
cd backend
python3 -m pip install -r requirements.txt
export PYTHONPATH=.
uvicorn app.main:app --reload
```

## Run tests

```bash
cd backend
export PYTHONPATH=.
pytest
```

## Docker deployment

The stack is prepared for Docker Compose:

```bash
docker compose up --build
```

Services:

- Backend API: `http://localhost:8000`
- Flutter web dashboard: `http://localhost:8080`
- PostgreSQL: `localhost:5432`

## Broker notes

### Binance

- Configure `BINANCE_API_KEY` and `BINANCE_API_SECRET`
- Public market data works without credentials
- Live orders require `PAPER_TRADING=false`

### MetaTrader5

- Requires a compatible host with MetaTrader5 Python support and an installed terminal
- Set `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`, and optionally `MT5_PATH`
- If MT5 is unavailable, the executor safely falls back to simulation

## Flutter mobile app

The `frontend/` directory contains the Flutter dashboard source. In a Flutter-enabled environment:

```bash
cd frontend
flutter create . --platforms android,ios,web
flutter pub get
flutter run
```

For containerized preview, the provided frontend Dockerfile builds the same Flutter app for the web and proxies API requests to the backend.
