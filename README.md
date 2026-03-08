# AI Automated Trading Bot (Forex + Crypto)

Production-oriented Python trading bot with:
- **Forex execution via MetaTrader5**
- **Crypto execution via Binance**
- **Liquidity Sweep + Break of Structure + Pullback strategy**
- **Multi-timeframe logic**: H1 bias, M15 structure, M5 execution
- **Risk controls**: 0.75% risk/trade, 15% max drawdown, max 3 trades/session
- **Trade management**: ATR or structure stop, TP1/TP2/TP3 ladder, break-even after TP1
- **AI layer**: RandomForest confidence scoring
- **Filters**: high-impact news + London/New York session filter
- **Modes**: paper trading and live trading
- **Infra**: FastAPI + PostgreSQL + Docker (24/7 background service)

> **Important**: This software is for educational/engineering use. Live trading carries significant risk.

---

## Architecture

```text
FastAPI control plane
  └── TradingEngine (background loop, 24/7)
      ├── MarketDataService (MT5 / Binance / synthetic fallback for paper)
      ├── Strategy (Liquidity Sweep + BOS + Pullback MTF)
      ├── Filters (news + sessions)
      ├── RiskManager (sizing + drawdown + session trade cap)
      ├── AIService (RandomForest confidence)
      └── TradeService (open/update/partials/BE management)
              ├── MT5Executor (forex live)
              ├── BinanceExecutor (crypto live)
              └── PaperExecutor (paper mode)
```

---

## Strategy Logic

1. **H1 bias**
   - EMA(20) and EMA(50) alignment sets bullish/bearish bias.
2. **M15 structure**
   - Liquidity sweep detection (wick sweep and close back inside range).
   - Break of Structure (close beyond prior range).
3. **M5 execution**
   - Pullback to mid-impulse area for entry.
4. **Stops and targets**
   - SL: ATR-based (default) or structure-based.
   - TP1 = 1R, TP2 = 1.5R, TP3 = 2R.
   - Stop moves to break-even after TP1.

---

## Risk & Session Rules

- Account balance baseline: **$3000**
- Risk per trade: **0.75%**
- Max drawdown kill-switch: **15%**
- Max trades per session/day: **3**
- Session filter: **London + New York**
- News filter: blocks near high-impact events (configurable cooldown)

---

## API Endpoints

- `GET /health`
- `GET /status`
- `POST /bot/start`
- `POST /bot/stop`
- `POST /bot/run-once`
- `POST /ai/train`
- `GET /trades`
- `GET /trades/{trade_id}`

---

## Quick Start (Docker, recommended)

1. Copy env:
   ```bash
   cp .env.example .env
   ```

2. Start stack:
   ```bash
   docker compose up --build -d
   ```

3. Check health:
   ```bash
   curl http://localhost:8000/health
   ```

The bot starts automatically in the FastAPI lifespan and runs in a background loop.

---

## Local Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

---

## Live Mode Setup

In `.env`:
- `TRADING_MODE=live`
- Fill MT5 credentials (`MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`)
- Fill Binance credentials (`BINANCE_API_KEY`, `BINANCE_API_SECRET`)

If credentials are missing in live mode, startup fails fast.

---

## AI Model

- Stored at `models/random_forest.joblib`.
- Confidence score blends ML probability and rule score.
- Retraining endpoint: `POST /ai/train`.

---

## Notes for Production

- Add proper broker symbol precision/lot constraints per instrument.
- Consider websocket data feeds for lower latency.
- Add robust circuit breakers and alerting (Slack/Telegram).
- Add audit/event tables and reporting dashboards.

