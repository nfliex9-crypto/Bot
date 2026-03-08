# AI Automated Trading Bot

Professional 24/7 automated trading system for **Forex (MetaTrader5)** and **Crypto (Binance)**.

## Strategy

- **Liquidity Sweep** – Price sweeps liquidity zones then reverses
- **Break of Structure (BOS)** – Trend continuation on structure break
- **Pullback Entry** – Entry on pullback to structure in trend

## Multi-Timeframe Analysis

| Timeframe | Role |
|-----------|------|
| H1 | Market bias |
| M15 | Trend structure |
| M5 | Execution |

## Risk Management

- Account balance: $3,000 (configurable)
- Risk per trade: 0.75%
- Max drawdown: 15%
- Max trades per session: 3

## Trade Management

- **Stop loss**: ATR-based or structure-based
- **TP1** = 1R, **TP2** = 1.5R, **TP3** = 2R
- Break-even after TP1

## AI Layer

- RandomForest classifier for trade confidence
- Confidence threshold: 0.6 minimum

## Filters

- **Session filter**: London + New York hours only
- **News filter**: High-impact news buffer (extensible)

## Modes

- **Paper trading** – Simulated execution (default)
- **Live trading** – Real execution via MT5/Binance

---

## Quick Start

### 1. Environment

```bash
cp .env.example .env
# Edit .env with your credentials (optional for paper mode)
```

### 2. Docker (recommended)

```bash
docker-compose up -d
```

- API: http://localhost:8000
- Celery worker runs trading cycles every 5 minutes
- PostgreSQL and Redis included

### 3. Local development

```bash
pip install -r requirements.txt

# Start PostgreSQL and Redis (or use Docker for them only)
# Then:

# API server
uvicorn app.main:app --reload

# Or standalone (no Redis) - cycles every 5 min
python run_bot.py --standalone

# Or full Celery stack
celery -A app.worker.celery_app worker --loglevel=info &
celery -A app.worker.celery_app beat --loglevel=info &
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TRADING_MODE` | `paper` | `paper` or `live` |
| `ACCOUNT_BALANCE` | 3000 | Starting balance |
| `RISK_PER_TRADE` | 0.75 | % risk per trade |
| `MAX_DRAWDOWN` | 15 | Max drawdown % |
| `MAX_TRADES_PER_SESSION` | 3 | Trades per London session |
| `MT5_LOGIN` | - | MT5 account |
| `MT5_PASSWORD` | - | MT5 password |
| `MT5_SERVER` | - | MT5 server |
| `BINANCE_API_KEY` | - | Binance API key |
| `BINANCE_API_SECRET` | - | Binance API secret |
| `BINANCE_TESTNET` | true | Use Binance testnet |

---

## API Endpoints

- `GET /` – Status
- `GET /health` – Health check
- `GET /trades` – List trades
- `POST /run-cycle` – Manually trigger one cycle

---

## Architecture

```
app/
├── main.py           # FastAPI app
├── engine.py         # Trading engine orchestrator
├── core/             # Strategy, risk, indicators
├── execution/        # MT5, Binance adapters
├── ai/               # RandomForest classifier
├── filters/          # Session, news filters
├── database/         # PostgreSQL models
└── worker/           # Celery tasks
```

---

## MT5 Setup

1. Install MetaTrader 5
2. Set `MT5_PATH` to terminal64.exe path (Windows) if needed
3. Provide login, password, server in `.env`

## Binance Setup

1. Create API keys at Binance (or testnet)
2. Set `BINANCE_API_KEY`, `BINANCE_API_SECRET`
3. Use `BINANCE_TESTNET=true` for paper/sandbox

---

## License

Apache 2.0
