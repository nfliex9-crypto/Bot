# AI Trading Bot

Production-style automated trading bot for:

- Forex via MetaTrader 5
- Crypto via Binance

The platform combines:

- Multi-timeframe strategy logic
- RandomForest confidence scoring
- Risk and drawdown controls
- Paper mode and live mode
- FastAPI monitoring and control endpoints
- PostgreSQL persistence
- Docker deployment for 24/7 operation

## Strategy

The worker trades a three-layer structure model:

- **H1**: market bias
- **M15**: break of structure confirmation
- **M5**: liquidity sweep plus pullback entry

Trade management rules:

- ATR stop loss or structure stop option
- TP1 = 1R
- TP2 = 1.5R
- TP3 = 2R
- Stop moves to break-even after TP1

Risk defaults:

- Account balance: **$3000**
- Risk per trade: **0.75%**
- Max drawdown: **15%**
- Max trades per session: **3**

Trading filters:

- London and New York session filter
- High-impact news blackout filter

## Architecture

### Services

- **api**: FastAPI app for health, status, trade history, signal history, bot enable/disable, and AI retraining
- **worker**: background process that runs continuously, scans markets, generates setups, executes trades, and manages open positions
- **postgres**: durable storage for trades, signals, and bot state

### Core modules

- `app/services/strategy.py`: liquidity sweep + BOS + pullback setup generation
- `app/services/ai.py`: RandomForest-based confidence scoring and training pipeline
- `app/services/risk.py`: position sizing, session trade limits, drawdown guardrails
- `app/services/filters.py`: session and news filtering
- `app/services/execution.py`: paper execution plus live execution routing for Binance and MT5
- `app/services/engine.py`: continuous orchestration loop

## MT5 support on Linux

MetaTrader 5 direct Python execution is often tied to environments where the MT5 terminal is available. This project supports two MT5 modes:

- `MT5_CONNECTION_MODE=direct`: use the optional `MetaTrader5` Python package on a compatible host
- `MT5_CONNECTION_MODE=bridge`: connect to an external MT5 bridge service over HTTP

For Dockerized Linux deployments, the **bridge mode** is usually the practical choice.

Expected bridge endpoints:

- `GET /rates?symbol=EURUSD&timeframe=M5&limit=300`
- `GET /price?symbol=EURUSD`
- `POST /orders`
- `POST /orders/close`

## Binance support

Binance live execution uses the `python-binance` client. By default, the code is wired for Binance Futures so both long and short strategies can be expressed. Set `BINANCE_FUTURES=false` if you want to adapt it to spot trading.

## Quick start

### 1. Configure environment

```bash
cp .env.example .env
```

Update credentials and connection settings:

- Binance API key/secret
- MT5 bridge URL or MT5 direct credentials
- Trading mode (`paper` or `live`)

### 2. Run with Docker

```bash
docker compose up --build
```

This starts:

- PostgreSQL on `localhost:5432`
- API on `localhost:8000`
- Worker as a background service

### 3. Local development

```bash
python3 -m pip install -e .[dev]
uvicorn app.main:app --host 0.0.0.0 --port 8000
python3 -m app.worker
```

## API endpoints

- `GET /health`
- `GET /status`
- `POST /bot/enable`
- `POST /bot/disable`
- `GET /trades`
- `GET /signals`
- `POST /ai/train`

## AI model lifecycle

The worker logs engineered feature vectors alongside each trade. Once a sufficient number of trades has closed, retrain the RandomForest model:

```bash
curl -X POST http://localhost:8000/ai/train
```

If the model has not yet been trained, the engine falls back to a blended heuristic confidence score derived from strategy confluence.

## Paper trading vs live trading

- `TRADING_MODE=paper`: all orders are simulated, while risk, TP logic, break-even logic, and database tracking stay active
- `TRADING_MODE=live`: execution is routed to Binance or MT5 based on market type

## Operational notes

- Run the worker continuously for 24/7 trading.
- Keep API and worker as separate processes so monitoring does not interfere with execution.
- For production, place the services behind proper secrets management, logging, and observability.
- News feeds can fail intermittently; the bot is configured to fail open by default unless `NEWS_FAIL_OPEN=false`.

## Testing

```bash
pytest
```
