# AI Automated Trading System

Cloud-ready automated trading stack with:

- **Backend**: FastAPI, Pandas, NumPy, scikit-learn, PostgreSQL
- **Strategy**: Liquidity sweep + break of structure + pullback entry
- **Markets**: Forex (MetaTrader5 adapter) + Crypto (Binance adapter)
- **Risk engine**: 0.75% risk/trade, 15% max drawdown, 3 trades/session, ATR stops, TP1/TP2/TP3, break-even after TP1
- **AI layer**: Random Forest confidence model
- **Execution engine**: MT5/Binance order routing with paper mode fallback
- **Frontend**: Flutter mobile dashboard
- **Deployment**: Docker + Docker Compose

## Repository Structure

```
backend/
  app/
    ai/
    db/
    execution/
    market/
    risk/
    services/
    strategy/
    main.py
frontend/
  lib/
docker-compose.yml
```

## Quick Start

1. Copy env file:

```bash
cp .env.example .env
```

2. Start backend + PostgreSQL:

```bash
docker compose up --build
```

3. Open API docs:

- http://localhost:8000/docs

## Core API Endpoints

- `GET /health`
- `POST /trading/cycle` -> runs one signal-generation + execution cycle
- `GET /dashboard/equity`
- `GET /dashboard/trades`
- `GET /dashboard/signals/live`
- `POST /ai/train`

## Flutter App

The Flutter app consumes backend APIs and displays:

- Equity
- Trade history
- AI confidence
- Live signals

Run locally:

```bash
cd frontend
flutter pub get
flutter run
```

## Notes

- MT5 is implemented as an adapter and degrades gracefully when unavailable in Linux containers.
- Binance integration supports testnet mode.
- If `TRADING_ENABLED=false`, system runs in signal-only / paper-safe mode.
