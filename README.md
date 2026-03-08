# AI Automated Trading Bot (Forex MT5 + Crypto Binance)

Professional, production-style trading system with:

- **Markets**: Forex (MetaTrader5), Crypto (Binance)
- **Strategy**: Liquidity Sweep + Break of Structure + Pullback Entry
- **Multi-timeframe flow**:
  - H1: market bias
  - M15: trend structure / BOS
  - M5: execution timing
- **Risk management**:
  - Account balance: **$3000**
  - Risk per trade: **0.75%**
  - Max drawdown: **15%**
  - Max trades per session: **3**
- **Trade management**:
  - ATR stop-loss (or structure stop option)
  - TP1 = 1R, TP2 = 1.5R, TP3 = 2R
  - Break-even after TP1
- **AI layer**:
  - RandomForest confidence model
  - Confidence-based trade filtering
- **Filters**:
  - High-impact news filter
  - Session filter (London + New York)
- **Infrastructure**:
  - Python, FastAPI, Pandas, NumPy, PostgreSQL, Docker
- **Modes**:
  - Paper trading
  - Live trading

---

## 1) Architecture

```text
app/
  main.py                     # FastAPI app + scheduler loop
  config.py                   # Environment configuration
  ai/model.py                 # RandomForest confidence scorer
  strategy/                   # Liquidity sweep / BOS / pullback logic
  risk/manager.py             # Risk sizing + drawdown / trade caps
  services/
    bot_service.py            # Bot orchestration per cycle
    trade_manager.py          # TP/SL/BE progression
    session_filter.py         # London/NY filter
    news_filter.py            # High-impact event filter
  market/
    mt5_client.py             # MT5 OHLC data adapter
    binance_client.py         # Binance OHLC data adapter
  execution/
    paper.py                  # Paper execution
    mt5_executor.py           # Live forex execution
    binance_executor.py       # Live crypto execution
  db/
    models.py                 # Trade + bot state tables
    init_db.py                # Schema bootstrap
scripts/train_model.py        # RandomForest model training
```

Bot loop runs every 60 seconds by default and is designed for **24/7 background operation**.

---

## 2) Setup

### A. Environment

```bash
cp .env.example .env
```

Edit `.env` with real credentials for MT5/Binance when using live mode.

### B. Run with Docker (recommended)

```bash
docker compose up -d --build
```

This starts:
- `db` (PostgreSQL)
- `bot` (FastAPI + scheduler)

Background resilience:
- `restart: unless-stopped`
- scheduler-driven continuous cycle

---

## 3) API Endpoints

- `GET /health` → service health + mode
- `GET /bot/status` → runtime status, equity, drawdown, open trades
- `POST /bot/control` with `{"running": true|false}` → pause/resume bot
- `POST /bot/run-once` → immediate strategy cycle
- `GET /trades/open` → currently open positions
- `GET /trades/history?limit=50` → latest trade records

---

## 4) Paper vs Live

Set:

```env
TRADING_MODE=paper
```

or

```env
TRADING_MODE=live
```

Behavior:
- `paper`: all orders are simulated and persisted.
- `live`: forex routed to MT5 executor, crypto routed to Binance executor.

---

## 5) AI Confidence Layer

The bot uses `TradeConfidenceModel` (RandomForest) to score setups.

- If model artifact exists at `MODEL_PATH`, it is used.
- Otherwise fallback confidence is used until training is performed.

Train/update model:

```bash
python -m scripts.train_model
```

This uses historical closed trades from DB (or synthetic bootstrap data if history is insufficient).

---

## 6) Safety and Risk Notes

- The risk manager blocks new trades if drawdown reaches configured max.
- Session cap enforces max 3 trades per session/day key.
- Break-even logic is applied immediately after TP1.
- News filter can block entries ahead of high-impact events.
- Start in **paper mode first** and validate execution, spread/slippage assumptions, and symbol sizing rules per broker.

---

## 7) Production Hardening Checklist (recommended)

- Add broker-specific lot sizing normalization and symbol precision rules.
- Add robust retry/backoff and circuit breakers around exchange APIs.
- Add unit/integration tests (strategy, risk manager, execution adapters).
- Add observability stack (structured logs, metrics, alerting).
- Add migrations (Alembic) and secrets manager integration.
- Add kill-switch endpoint with authentication.

