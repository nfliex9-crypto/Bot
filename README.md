# AI Automated Trading Bot

Professional AI-powered automated trading bot for **Forex** (via MetaTrader 5) and **Crypto** (via Binance), featuring smart money concepts (SMC) strategy with machine learning confidence scoring.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Dashboard                        │
│              /api/v1/status  /trades  /signals               │
└───────────────────────┬─────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────┐
│                   Bot Orchestrator                            │
│         5-min cycle: scan → analyse → execute → manage       │
├──────────┬──────────┬──────────┬──────────┬─────────────────┤
│  News    │ Session  │    AI    │   Risk   │     Trade       │
│  Filter  │ Filter   │ Scorer   │ Manager  │    Manager      │
├──────────┴──────────┴──────────┴──────────┴─────────────────┤
│                    Strategy Engine                            │
│        Liquidity Sweep → BOS Confirm → Pullback Entry        │
├─────────────────────────────────────────────────────────────┤
│              Multi-Timeframe Analysis                         │
│            H1 (bias) → M15 (structure) → M5 (entry)         │
├───────────────────┬─────────────────────────────────────────┤
│   MT5 Provider    │           Binance Provider               │
├───────────────────┼─────────────────────────────────────────┤
│   MT5 Executor    │   Binance Executor  │  Paper Executor   │
└───────────────────┴─────────────────────┴───────────────────┘
                        │
                  ┌─────▼─────┐
                  │ PostgreSQL │
                  └───────────┘
```

## Strategy

**Liquidity Sweep → Break of Structure → Pullback Entry**

1. **H1 Bias** — Determine market direction from higher-timeframe swing structure (higher highs / lower lows)
2. **M15 Structure** — Confirm break-of-structure (BOS) or change-of-character (CHoCH) aligned with H1 bias
3. **M5 Execution** — Detect liquidity sweep (stop-hunt wick), then enter on pullback to EMA-21

### Trade Management

| Level | Target | Action |
|-------|--------|--------|
| TP1   | 1.0R   | Close 33%, move SL to break-even |
| TP2   | 1.5R   | Close 33% |
| TP3   | 2.0R   | Close remaining |

### Risk Management

- Account balance: $3,000
- Risk per trade: 0.75%
- Max drawdown: 15%
- Max trades per session: 3

## AI Layer

- **RandomForest classifier** trained on trade setup features
- Features: H1 bias alignment, BOS count, pullback distance, RSI, ATR, EMA distance, sweep wick size
- Minimum confidence threshold: 65%
- Auto-retrains as real trade data accumulates

## Quick Start

### With Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your API keys

docker compose up -d
```

The bot starts at `http://localhost:8000`.

### Without Docker

```bash
pip install -r requirements.txt

# Start PostgreSQL and set DATABASE_URL in .env
cp .env.example .env

python main.py
```

## Configuration

All settings are in `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `TRADING_MODE` | `paper` | `paper` or `live` |
| `MT5_LOGIN` | — | MetaTrader 5 account login |
| `MT5_PASSWORD` | — | MT5 password |
| `MT5_SERVER` | — | MT5 broker server |
| `BINANCE_API_KEY` | — | Binance API key |
| `BINANCE_API_SECRET` | — | Binance API secret |
| `BINANCE_TESTNET` | `true` | Use Binance testnet |
| `ACCOUNT_BALANCE` | `3000` | Starting balance |
| `RISK_PER_TRADE` | `0.75` | Risk % per trade |
| `MAX_DRAWDOWN_PCT` | `15.0` | Max drawdown % |
| `MAX_TRADES_PER_SESSION` | `3` | Session trade limit |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/status` | Bot status, balance, drawdown |
| GET | `/api/v1/trades` | Trade history |
| GET | `/api/v1/signals` | Signal history |
| GET | `/api/v1/performance` | Win rate, PnL, profit factor |
| GET | `/api/v1/ai/model` | AI model info + feature importance |
| POST | `/api/v1/bot/start` | Start bot |
| POST | `/api/v1/bot/stop` | Stop bot |
| POST | `/api/v1/bot/reset-session` | Reset session trade count |

Interactive docs available at `/docs` (Swagger UI).

## Scripts

```bash
# Train / retrain the AI classifier
python scripts/train_model.py

# Run backtest on synthetic data
python scripts/run_backtest.py
```

## Testing

```bash
python -m pytest tests/ -v
```

## Project Structure

```
├── app/
│   ├── ai/                  # RandomForest classifier + feature engineering
│   ├── analysis/            # Indicators, market structure, MTF analysis
│   ├── api/                 # FastAPI routes + schemas
│   ├── core/                # Config, database, logging
│   ├── execution/           # MT5, Binance, Paper executors
│   ├── filters/             # News filter, session filter
│   ├── market_data/         # MT5 + Binance data providers
│   ├── models/              # SQLAlchemy ORM models
│   ├── risk/                # Position sizing + risk management
│   ├── strategy/            # Liquidity sweep, BOS, pullback entry
│   ├── trade_management/    # TP/SL/break-even management
│   ├── utils/               # Helper functions
│   └── bot.py               # Main orchestrator
├── tests/                   # Test suite (34 tests)
├── scripts/                 # Training + backtesting scripts
├── alembic/                 # Database migrations
├── docker-compose.yml       # Full stack: bot + PostgreSQL + Redis
├── Dockerfile
├── main.py                  # Entry point
└── requirements.txt
```
