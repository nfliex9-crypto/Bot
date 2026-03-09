# AI Automated Trading Bot

A professional, production-ready AI trading bot for Forex (MetaTrader 5) and Crypto (Binance).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FastAPI REST API                         │
│          /api/v1/bot • /trades • /signals • /performance    │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   Trading Bot Core                          │
│    Scanner (60s) → Execute → Monitor → Manage Lifecycle     │
└──┬──────────────────────────────────────────────────────────┘
   │
   ├─ Multi-Timeframe Analyzer
   │    H1 (bias) → M15 (trend) → M5 (execution)
   │
   ├─ Strategy Engine
   │    1. Liquidity Sweep Detection
   │    2. Break of Structure (BOS/CHoCH)
   │    3. Pullback Entry (FVG / Order Block / 50%)
   │
   ├─ AI Layer (RandomForest)
   │    Feature engineering → Confidence score → Gate trades
   │
   ├─ Risk Manager
   │    Position sizing • Drawdown check • Session limits
   │
   ├─ Filters
   │    Session (London/NY) • High-impact news
   │
   └─ Broker Connectors
        MT5 Broker (Forex) • Binance Broker (Crypto)
```

## Strategy: Smart Money Concepts (SMC)

### 1. Liquidity Sweep
Price "hunts" liquidity above swing highs (buy-side) or below swing lows (sell-side).
A valid sweep: price wicks through the level, candle closes back past it with rejection.

### 2. Break of Structure (BOS)
After the sweep, price breaks the opposing swing structure confirming reversal direction:
- **CHoCH** (Change of Character): First structural break (weaker confirmation)
- **BOS** (Break of Structure): Confirmed candle close beyond key level (stronger)

### 3. Pullback Entry
Enter on retracement into a confluence zone:
1. **FVG** (Fair Value Gap): Imbalance from the impulse move
2. **OB** (Order Block): Last opposing candle before the BOS impulse
3. **50% Retracement**: Mid-point of the impulse leg
4. **BOS Level**: Previous structure now acting as support/resistance

## Risk Management

| Parameter | Value |
|-----------|-------|
| Account Balance | $3,000 |
| Risk Per Trade | 0.75% ($22.50) |
| Max Drawdown | 15% |
| Max Trades/Session | 3 |
| TP1 | 1R (break-even after) |
| TP2 | 1.5R |
| TP3 | 2R |
| Stop Loss | ATR-based or Structure |

## Trading Sessions

| Session | UTC Time | Status |
|---------|----------|--------|
| London | 08:00–16:00 | Active |
| New York | 13:00–21:00 | Active |
| Overlap | 13:00–16:00 | Active (highest priority) |
| Off-session | Other times | Forex paused, Crypto continues |

## Multi-Timeframe Analysis

| Timeframe | Role |
|-----------|------|
| H1 | Market bias (bullish/bearish) via EMA + swing structure |
| M15 | Trend confirmation + sweep/BOS search |
| M5 | Precise execution entry |

## AI Layer

- **Model**: RandomForest Classifier (200 trees, max depth 10)
- **Features**: 40 features including price structure, indicators, sweep/BOS, MTF alignment
- **Confidence threshold**: 0.65 (configurable)
- **Fallback**: Rule-based heuristic scoring when no model is loaded
- **Training**: `scripts/train_model.py` (bootstraps with synthetic data until real trades accumulate)

## Quick Start

### Paper Trading (Recommended First)

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start with Docker Compose
docker-compose up -d

# 3. Access the API
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/bot/status
```

### With Monitoring (Grafana + Prometheus)

```bash
docker-compose --profile monitoring up -d
# Grafana: http://localhost:3000 (admin/trading_admin)
# Prometheus: http://localhost:9090
```

## Configuration

Edit `.env` or set environment variables:

```bash
# Core
TRADING_MODE=paper          # paper | live
ACCOUNT_BALANCE=3000.0

# Risk
RISK_PER_TRADE=0.0075       # 0.75%
MAX_DRAWDOWN=0.15            # 15%
MAX_TRADES_PER_SESSION=3

# AI
MIN_CONFIDENCE=0.65

# MT5 (for live Forex, Windows only)
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=MetaQuotes-Demo

# Binance (for live Crypto)
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret
BINANCE_TESTNET=true         # false for mainnet
```

## API Endpoints

### Bot Control
```
GET  /api/v1/bot/status     - Bot status and stats
POST /api/v1/bot/start      - Start the bot
POST /api/v1/bot/stop       - Stop the bot
POST /api/v1/bot/pause      - Pause scanning
POST /api/v1/bot/resume     - Resume scanning
GET  /api/v1/bot/config     - View configuration
GET  /api/v1/bot/health     - Health check
```

### Trades
```
GET  /api/v1/trades/          - List trades (with filters)
GET  /api/v1/trades/open      - Open trades
GET  /api/v1/trades/today     - Today's trades
GET  /api/v1/trades/{id}      - Single trade detail
GET  /api/v1/trades/stats/summary - P&L stats
```

### Signals
```
GET  /api/v1/signals/           - All signals
GET  /api/v1/signals/latest     - Last N hours
GET  /api/v1/signals/{id}       - Signal detail
GET  /api/v1/signals/stats/by-symbol - Stats per symbol
```

### Performance
```
GET  /api/v1/performance/summary      - Full performance report
GET  /api/v1/performance/equity-curve - Equity curve data
GET  /api/v1/performance/by-session   - Session breakdown
GET  /api/v1/performance/risk-metrics - Live risk metrics
```

## Training the AI Model

```bash
# Bootstrap with synthetic data (first run)
python scripts/train_model.py --synthetic --n-synthetic 2000

# Train on real historical trades (after accumulating data)
python scripts/train_model.py --days 90

# Custom model path
python scripts/train_model.py --model-path ./models/my_model.pkl
```

## Backtesting

```bash
# Single symbol
python scripts/backtest.py --symbol EURUSD --days 30

# Crypto
python scripts/backtest.py --symbol BTCUSDT --market crypto --days 30

# All symbols
python scripts/backtest.py --all-symbols --days 60
```

## Automated Strategy Discovery

Discover profitable rule-based strategies automatically with walk-forward validation.

```bash
# Run on your historical OHLCV CSV
python scripts/discover_strategies.py --data-file ./data/BTCUSDT_M5.csv --n-strategies 240

# Local smoke test with synthetic data
python scripts/discover_strategies.py --use-synthetic --n-strategies 240
```

Outputs are exported to `outputs/strategy_discovery/`:
- `top_5_strategies.json`
- `top_5_report.md`
- `all_survivors.json`
- `summary.json`

The best discovered strategy is auto-converted to:
- `app/core/strategy/discovered_auto.py`

This generated module returns `EntryResult` objects compatible with the current trading engine conventions.

## Project Structure

```
trading-bot/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration (env vars)
│   ├── database.py          # Async PostgreSQL setup
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic schemas
│   ├── api/routes/          # FastAPI route handlers
│   ├── core/
│   │   ├── strategy/
│   │   │   ├── liquidity_sweep.py
│   │   │   ├── break_of_structure.py
│   │   │   ├── pullback_entry.py
│   │   │   └── multi_timeframe.py
│   │   ├── ai/
│   │   │   ├── classifier.py  # RandomForest
│   │   │   └── features.py    # Feature engineering
│   │   ├── risk_manager.py
│   │   ├── trade_manager.py
│   │   ├── session_filter.py
│   │   └── news_filter.py
│   ├── brokers/
│   │   ├── base.py
│   │   ├── mt5_broker.py    # MetaTrader 5
│   │   └── binance_broker.py
│   ├── bot/
│   │   ├── trading_bot.py   # Main orchestrator
│   │   └── scanner.py       # Market scanner
│   └── utils/
│       ├── logger.py
│       └── indicators.py    # Technical indicators
├── scripts/
│   ├── train_model.py       # ML model training
│   └── backtest.py          # Strategy backtesting
├── alembic/                 # Database migrations
├── models/                  # Saved ML models
├── logs/                    # Application logs
├── monitoring/              # Prometheus/Grafana config
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## MetaTrader 5 Note

The MT5 Python library only works on **Windows**. On Linux/Docker:
- The bot runs in **paper mode** for all MT5 instruments
- To use live MT5 trading: deploy on a Windows machine or Windows VM
- Binance (crypto) works fully on Linux without any restrictions

## Live Trading Warning

⚠️ **Use at your own risk.** This is an automated trading system that can lose money.
Before switching to live mode:
1. Run in paper mode for at least 30 days
2. Review backtest results across multiple market conditions
3. Start with the minimum position size
4. Monitor closely for the first week
5. Set your broker's account max drawdown as a hard stop
