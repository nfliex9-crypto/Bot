# AI Automated Trading Bot

A professional-grade automated trading system for **Forex** (MetaTrader 5) and **Crypto** (Binance) markets. Features AI-powered signal scoring, multi-timeframe analysis, and comprehensive risk management.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Dashboard (:8000)                │
│              Status │ Trades │ Signals │ Controls            │
├─────────────────────────────────────────────────────────────┤
│                      Bot Engine (24/7 Loop)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Session   │  │  News    │  │   Risk   │  │     AI     │  │
│  │ Filter    │  │  Filter  │  │ Manager  │  │  Scorer    │  │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                  MTF Strategy Analyzer                       │
│  ┌────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│  │ H1 Bias    │  │ M15 Structure   │  │ M5 Execution     │  │
│  │ Detection  │  │ BOS / CHoCH     │  │ Pullback Entry   │  │
│  └────────────┘  └─────────────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                   Execution Layer                            │
│  ┌───────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ MT5       │  │ Binance      │  │ Paper (Simulated)    │  │
│  │ Executor  │  │ Executor     │  │ Executor             │  │
│  └───────────┘  └──────────────┘  └──────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL │ Candles │ Trades │ Signals │ Account Snapshots │
└─────────────────────────────────────────────────────────────┘
```

## Strategy

The bot implements a Smart Money Concepts (SMC) strategy:

1. **Liquidity Sweep** — Detects stop hunts beyond swing highs/lows where price wicks past a level then reverses
2. **Break of Structure (BOS)** — Identifies when price closes beyond the most recent swing point, confirming trend continuation
3. **Pullback Entry** — Waits for 50-61.8% Fibonacci retracement of the impulse leg with candlestick rejection

### Multi-Timeframe Analysis

| Timeframe | Role | Analysis |
|-----------|------|----------|
| **H1** | Market Bias | Higher highs/lows = bullish, lower highs/lows = bearish |
| **M15** | Trend Structure | Break of Structure detection, liquidity zone mapping |
| **M5** | Execution | Pullback entries, precise stop placement |

## Risk Management

| Parameter | Value |
|-----------|-------|
| Account Balance | $3,000 |
| Risk Per Trade | 0.75% ($22.50) |
| Max Drawdown | 15% |
| Max Trades/Session | 3 |
| Stop Loss | ATR-based (1.5x ATR) |
| TP1 | 1R (partial close 33%) |
| TP2 | 1.5R (partial close 50%) |
| TP3 | 2R (close remaining) |
| Break-Even | After TP1 hit |

## AI Layer

- **RandomForest Classifier** trained on historical trade outcomes
- **14 features**: ATR values, RSI, volume ratio, body ratio, EMA spread, bias indicators, signal type, R:R ratio, liquidity zone count
- **Auto-retrain** every 24 hours with latest closed trade data
- **Confidence threshold** (default 60%) gates trade execution

## Quick Start

### Docker (Recommended)

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# 2. Start services
docker compose up -d

# 3. View dashboard
open http://localhost:8000
```

### Manual

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start PostgreSQL
# (ensure PostgreSQL is running on localhost:5432)

# 3. Configure
cp .env.example .env
# Edit .env

# 4. Run
python main.py
```

## Configuration

All settings are configured via environment variables (`.env` file):

### Trading Mode

```
TRADING_MODE=paper    # paper = simulated execution, live = real orders
```

### MetaTrader 5 (Forex)

```
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
MT5_SERVER=MetaQuotes-Demo
```

### Binance (Crypto)

```
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
BINANCE_TESTNET=true
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web dashboard |
| `/health` | GET | Health check |
| `/api/controls/status` | GET | Bot status & account info |
| `/api/controls/stop` | POST | Stop the engine |
| `/api/controls/close-all` | POST | Close all open trades |
| `/api/trades/open` | GET | List open trades |
| `/api/trades/closed` | GET | List closed trades |
| `/api/trades/today` | GET | Today's trades |
| `/api/dashboard/account-history` | GET | Account balance history |
| `/api/dashboard/recent-signals` | GET | Recent signal log |
| `/api/dashboard/performance` | GET | Win rate & P/L stats |

## Project Structure

```
├── ai/                  # AI model, features, confidence scoring
├── api/                 # FastAPI app + dashboard
│   └── routes/          # API route handlers
├── bot/                 # Main trading engine
├── config/              # Settings & configuration
├── core/                # Enums, data models, event bus
├── data/                # Market data feeds & candle management
├── database/            # PostgreSQL models & repository
├── execution/           # Trade executors (MT5, Binance, Paper)
├── filters/             # Session & news filters
├── risk/                # Risk management
├── strategy/            # Liquidity, structure, pullback analysis
├── tests/               # Test suite
├── docker-compose.yml   # Docker orchestration
├── Dockerfile           # Container build
├── main.py              # Entry point
└── requirements.txt     # Python dependencies
```

## Testing

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

## Disclaimer

This software is for **educational purposes only**. Trading financial instruments involves substantial risk of loss. Past performance does not guarantee future results. Always start with paper trading mode and thoroughly test before risking real capital.
