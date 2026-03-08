# AI Automated Trading Bot (Forex + Crypto)

Production-style Python trading system with:

- **Forex execution** via **MetaTrader 5**
- **Crypto execution** via **Binance**
- **Strategy stack**: Liquidity Sweep + Break of Structure + Pullback Entry
- **Multi-timeframe logic**:
  - H1 = market bias
  - M15 = trend structure
  - M5 = execution trigger
- **Risk controls**:
  - Account size: `$3000`
  - Risk/trade: `0.75%`
  - Max drawdown: `15%`
  - Max trades/session: `3`
- **Trade management**:
  - ATR stop-loss or structure stop
  - TP1 = 1R, TP2 = 1.5R, TP3 = 2R
  - Break-even after TP1
- **AI layer**:
  - RandomForest classifier
  - Confidence scoring gate before execution
- **Filters**:
  - High-impact news window filter
  - Session filter (London + New York)
- **Infrastructure**:
  - FastAPI, Pandas, NumPy, PostgreSQL, Docker
  - 24/7 background runtime (`restart: always`)
  - **Paper mode** and **live mode**

---

## Architecture

```text
app/
  ai/                  # RandomForest confidence scoring
  api/                 # FastAPI schemas/endpoints
  core/                # settings, db, logging
  data/                # MT5/Binance OHLCV adapters
  execution/           # Paper, Binance, MT5 executors
  filters/             # News + session filters
  models/              # PostgreSQL entities
  risk/                # Drawdown/trade-count/position sizing
  strategy/            # Liquidity sweep + BOS + pullback + MTF alignment
  trading/             # Engine loop + TP/BE position manager
```

---

## Quick start

1. Copy env file:

```bash
cp .env.example .env
```

2. Start services:

```bash
docker compose up --build -d
```

3. Check health:

```bash
curl http://localhost:8000/health
```

4. Engine status:

```bash
curl http://localhost:8000/engine/status
```

The engine auto-starts by default (`AUTO_START_ENGINE=true`).

---

## Run without Docker

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Headless bot-only mode:

```bash
python -m app.bot_runner
```

---

## Modes

- `MODE=paper`: orders are simulated.
- `MODE=live`: routes orders to:
  - **MT5** for forex symbols
  - **Binance** for crypto symbols

If live credentials are missing for a market, the system safely falls back to paper execution for that market.

---

## API

- `GET /health`
- `POST /engine/start` body: `{"mode":"paper" | "live"}`
- `POST /engine/stop`
- `GET /engine/status`
- `GET /signals/latest?limit=20`

---

## AI model training

Train RandomForest from historical feature dataset:

```bash
python scripts/train_model.py --csv data/training_dataset.csv --target won
```

Required dataset format:

- Feature columns matching engine feature keys
- Binary target column (default `won`)

---

## High-impact news filtering

Seed planned events into PostgreSQL:

```bash
python scripts/seed_news.py --csv data/news_events.csv
```

CSV columns:

- `title`
- `currency` (e.g., `USD`, `EUR`)
- `impact` (`high`, `medium`, `low`)
- `starts_at` (ISO datetime)

The bot blocks new entries in the configured window around high-impact events.

---

## Notes for live deployment

- MT5 Python API may require a platform-specific runtime setup.
- Binance live mode requires valid API keys and permissions.
- Start in paper mode, validate logs and behavior, then move to live mode gradually.
- This project is a framework and should be validated with your broker constraints, slippage model, and compliance requirements before trading real capital.
