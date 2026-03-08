# AI Automated Trading Bot

A professional AI-powered automated trading system for Forex (via MetaTrader5) and Crypto (via Binance).

---

## Strategy

| Component | Description |
|---|---|
| **Liquidity Sweep** | Detects equal highs/lows and swing level sweeps indicating institutional moves |
| **Break of Structure** | Identifies BOS and CHoCH for trend continuation and reversal setups |
| **Pullback Entry** | Fibonacci OTE zone (50–79%) with Order Block and FVG validation |

### Multi-Timeframe Analysis
- **H1** — Market bias (bullish/bearish/ranging)
- **M15** — Trend structure (BOS/CHoCH confirmation)
- **M5** — Execution entry (sweep + pullback)

---

## Risk Management

| Parameter | Value |
|---|---|
| Account Balance | $3,000 |
| Risk Per Trade | 0.75% ($22.50) |
| Max Drawdown | 15% ($450) |
| Max Trades/Session | 3 |

### Trade Management
- **SL**: ATR × 1.5 + structure stop (below sweep wick)
- **TP1**: 1R — 33% position close
- **TP2**: 1.5R — 50% of remaining close
- **TP3**: 2R — Final position close
- **Break-Even**: Stop moved to entry + buffer after TP1

---

## AI Layer

A `RandomForestClassifier` (200 trees, calibrated probabilities) scores each signal with a confidence score [0, 1].

Features include:
- EMA cross differentials (H1/M15/M5)
- RSI values (all timeframes)
- BOS/sweep/pullback structure indicators
- Fibonacci retracement levels
- Candle body/wick ratios
- Session time encoding (sin/cos)

The model retrains every 24 hours using recent closed trade history stored in PostgreSQL.

---

## Architecture

```
src/
├── main.py                   # Entry point
├── bot/
│   └── orchestrator.py       # 24/7 main loop
├── strategy/
│   ├── multi_timeframe.py    # H1/M15/M5 analysis
│   ├── liquidity_sweep.py    # Sweep detection
│   ├── break_of_structure.py # BOS/CHoCH
│   ├── pullback_entry.py     # Fibonacci + OB + FVG
│   └── indicators.py         # ATR, EMA, RSI, etc.
├── ai/
│   ├── classifier.py         # RandomForest model
│   └── feature_engineering.py
├── risk/
│   └── risk_manager.py       # Position sizing, drawdown
├── execution/
│   ├── mt5_executor.py       # Forex order execution
│   └── binance_executor.py   # Crypto order execution
├── connectors/
│   ├── mt5_connector.py      # MT5 data feed
│   └── binance_connector.py  # Binance data feed
├── filters/
│   ├── session_filter.py     # London + NY session gate
│   └── news_filter.py        # High-impact news blackout
├── trade_management/
│   └── manager.py            # TP/SL/BE management
├── models/
│   └── database.py           # SQLAlchemy ORM models
└── api/
    ├── main.py               # FastAPI app
    └── routes/               # REST endpoints
```

---

## Quick Start

### 1. Clone and configure
```bash
cp .env.example .env
# Edit .env with your broker credentials
```

### 2. Start with Docker
```bash
docker-compose up -d
```

This starts:
- PostgreSQL database
- Redis cache
- Trading bot (24/7 loop)
- FastAPI monitoring API on http://localhost:8000

### 3. Paper trading (no broker needed)
```bash
pip install -r requirements.txt
TRADING_MODE=paper python -m src.main --with-api
```

### 4. Backtest a symbol
```bash
python scripts/backtest.py --symbol EURUSD --days 90
python scripts/backtest.py --symbol BTCUSDT --market crypto --days 30
```

---

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | System health check |
| `GET /api/v1/bot/status` | Bot status, session, risk |
| `POST /api/v1/bot/control` | start/stop/pause/resume/retrain_ai |
| `GET /api/v1/trades/open` | Current open positions |
| `GET /api/v1/trades/history/summary` | P&L summary (last N days) |
| `GET /api/v1/performance/` | Account performance metrics |
| `GET /api/v1/performance/equity_curve` | Equity curve data |
| `GET /api/v1/performance/by_symbol` | P&L breakdown by symbol |
| `GET /api/v1/performance/news` | Upcoming high-impact news |

Full interactive docs: http://localhost:8000/docs

---

## Environment Variables

```env
TRADING_MODE=paper          # paper | live
ACCOUNT_BALANCE=3000.0
RISK_PER_TRADE=0.0075       # 0.75%
MAX_DRAWDOWN_PCT=0.15        # 15%
MAX_TRADES_PER_SESSION=3

# MetaTrader5
MT5_LOGIN=your_login
MT5_PASSWORD=your_password
MT5_SERVER=your_broker_server
MT5_SYMBOLS=EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,GBPJPY,EURJPY

# Binance
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret
BINANCE_TESTNET=true
BINANCE_SYMBOLS=BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT

# Database
DATABASE_URL=postgresql+asyncpg://trader:password@localhost:5432/trading_bot
```

---

## Trading Mode

| Mode | Description |
|---|---|
| **Paper** | Simulated trades, tracks P&L in DB, no real orders |
| **Live** | Real orders via MT5/Binance APIs |

**Always run paper mode first.** Switch to live only after validating performance.

---

## Filters

- **Session Filter**: Only trades during London (07:00–16:00 UTC) and New York (12:00–21:00 UTC)
- **News Filter**: Blocks trades ±30 minutes around high-impact economic events (auto-fetched from ForexFactory)

---

## Running Tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

---

## License

MIT
