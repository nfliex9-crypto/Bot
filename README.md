# AI Trading Bot

Professional automated trading bot for:

- Forex via MetaTrader 5
- Crypto via Binance

The system combines:

- Liquidity sweep detection
- Break of structure confirmation
- Pullback-based execution
- Multi-timeframe analysis
  - H1 market bias
  - M15 structure
  - M5 execution
- Risk controls
  - $3000 default account balance
  - 0.75% risk per trade
  - 15% max drawdown
  - 3 trades per session
- Trade management
  - ATR and structure-aware stop placement
  - TP1 = 1R
  - TP2 = 1.5R
  - TP3 = 2R
  - Break-even move after TP1
- AI scoring
  - RandomForest classifier
  - Confidence thresholding
- Filters
  - High-impact news blackout
  - London and New York session filter
- Execution modes
  - Paper trading
  - Live trading

## Architecture

The bot is organized into clear services:

- `app/strategy/liquidity.py`
  - Multi-timeframe liquidity sweep / BOS / pullback logic
- `app/ai/model.py`
  - RandomForest training and confidence scoring
- `app/risk/manager.py`
  - Position sizing, drawdown protection, trade caps
- `app/filters/`
  - Session and high-impact news filters
- `app/execution/`
  - Paper broker
  - Binance live broker
  - MetaTrader 5 live broker
- `app/services/engine.py`
  - 24/7 orchestration loop, trade lifecycle management, partial exits
- `app/api/routes.py`
  - FastAPI control plane
- `app/db/`
  - PostgreSQL persistence for trades, bot state, and economic events

## Important live-trading notes

### MetaTrader 5

The MT5 integration is implemented, but the official `MetaTrader5` Python package typically requires a compatible MT5 terminal environment. In practice this is commonly run on a Windows host or a Linux setup with a properly supported MT5 bridge.

### Binance

The Binance broker implementation is designed for futures-style market orders so both long and short flows can be automated. Use symbols and account configuration that match your venue setup.

### News filter

High-impact news filtering supports:

- manual event ingestion through the API, or
- automated sync from `NEWS_SYNC_URL` if you provide a calendar endpoint

## API

Core endpoints:

- `GET /health`
- `GET /bot/status`
- `POST /bot/start`
- `POST /bot/stop`
- `POST /bot/mode`
- `GET /trades`
- `GET /news/events`
- `POST /news/events`
- `POST /ai/train`

## Local development

1. Copy the environment template:

```bash
cp .env.example .env
```

2. Install dependencies:

```bash
python3 -m pip install -e '.[dev]'
```

3. Train the sample AI model:

```bash
curl -X POST http://localhost:8000/ai/train
```

4. Run the API and background bot:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Docker

Start the stack:

```bash
docker compose up --build
```

This launches:

- FastAPI trading bot on port `8000`
- PostgreSQL on port `5432`

## Example mode switch

Switch to live mode:

```bash
curl -X POST http://localhost:8000/bot/mode \
  -H "Content-Type: application/json" \
  -d '{"mode":"live"}'
```

Stop the engine from entering new positions:

```bash
curl -X POST http://localhost:8000/bot/stop
```

Resume the engine:

```bash
curl -X POST http://localhost:8000/bot/start
```

## Test suite

```bash
python3 -m pytest -q
```

## Default strategy behavior

- Trades are only considered during London or New York sessions.
- If high-impact events affect the symbol currencies within the configured blackout window, new trades are blocked.
- H1 establishes directional bias.
- M15 looks for a liquidity sweep and break of structure.
- M5 requires a pullback into structure before entry.
- After a trade opens, the engine manages partial exits and break-even movement automatically.

## Deployment recommendation

Use `paper` mode first, confirm broker credentials and symbol formatting, then enable `live` mode.
