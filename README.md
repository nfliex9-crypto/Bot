# AI Automated Trading Bot

A professional AI-powered 24/7 trading bot for **Forex (MetaTrader 5)** and **Crypto (Binance)**.

## Strategy

**Entry logic — three-layer confirmation:**
1. **Liquidity Sweep** — detects institutional stop-hunting (wick beyond swing high/low with reversal close)
2. **Break of Structure (BOS)** — confirms direction change via a close beyond the last significant swing
3. **Pullback Entry** — waits for price to retrace into the 38.2%–61.8% Fibonacci zone with a confirmation candle

**Multi-timeframe alignment:**
| Timeframe | Role |
|-----------|------|
| H1 | Market bias (bullish / bearish / neutral) |
| M15 | Trend structure (uptrend / downtrend / ranging) |
| M5 | Execution (sweep + BOS + pullback) |

---

## Architecture

```
main.py                  ← Uvicorn / FastAPI entrypoint
├── api/                 ← REST API (FastAPI)
│   ├── app.py           ← App factory + lifespan
│   └── routes/
│       ├── control.py   ← Engine control endpoints
│       ├── trades.py    ← Trade history & stats
│       └── dashboard.py ← Equity curve, daily perf
├── core/
│   ├── engine.py        ← Master trading loop
│   ├── data_feed.py     ← Rolling OHLCV buffers
│   └── models.py        ← Domain data classes
├── strategy/
│   ├── liquidity_sweep.py
│   ├── break_of_structure.py
│   ├── pullback_entry.py
│   └── analyzer.py      ← MTF orchestrator
├── ai/
│   ├── feature_engineer.py  ← 36 features
│   └── classifier.py        ← RandomForest + calibration
├── risk/
│   └── risk_manager.py  ← Position sizing, SL, TP
├── execution/
│   ├── base_executor.py
│   ├── mt5_executor.py  ← MT5 (paper + live)
│   └── binance_executor.py  ← Binance Futures (paper + live)
├── filters/
│   ├── session_filter.py    ← London + NY sessions
│   └── news_filter.py       ← ForexFactory calendar
├── database/
│   ├── models.py        ← SQLAlchemy ORM models
│   └── connection.py    ← Async PostgreSQL engine
├── config/
│   └── settings.py      ← Pydantic settings
└── utils/
    ├── logger.py
    └── helpers.py
```

---

## Risk Management

| Parameter | Value |
|-----------|-------|
| Account balance | $3,000 |
| Risk per trade | 0.75% ($22.50) |
| Max drawdown | 15% |
| Max trades / session | 3 |
| Stop-loss | ATR × 1.5 or Structure (wider used) |
| TP1 | 1R — close 40% |
| TP2 | 1.5R — close 35% |
| TP3 | 2R — close 25% |
| Break-even | After TP1 hit |

---

## AI Layer

- **Algorithm:** `RandomForestClassifier` (200 trees, calibrated with Platt scaling)
- **Features:** 36 engineered features — ATR, RSI, MACD, Stochastic, CCI, Bollinger Bands, EMA slopes, swing levels, session flags, MTF alignment signals
- **Threshold:** Trades only execute when AI confidence ≥ 60%
- **Retraining:** Via API endpoint `POST /control/retrain-ai`

---

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 2. Run with Docker Compose

```bash
docker-compose up -d
```

This starts:
- `trading_bot` — the bot + API on port **8000**
- `db` — PostgreSQL on port **5432**
- `pgadmin` — Database admin UI on port **5050**

### 3. Run locally (development)

```bash
pip install -r requirements.txt
python main.py
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/docs` | GET | Swagger UI |
| `/control/status` | GET | Engine status, account state |
| `/control/pause` | POST | Pause trading |
| `/control/resume` | POST | Resume trading |
| `/control/open-trades` | GET | Live open positions |
| `/control/session` | GET | Current session + news |
| `/control/retrain-ai` | POST | Retrain AI classifiers |
| `/trades/` | GET | Trade history (filterable) |
| `/trades/stats` | GET | Win rate, P&L, avg RR |
| `/trades/signals` | GET | Signal log |
| `/trades/{trade_id}` | GET | Single trade detail |
| `/dashboard/summary` | GET | Full dashboard snapshot |
| `/dashboard/equity-curve` | GET | Equity curve data |
| `/dashboard/daily-performance` | GET | Daily P&L breakdown |

---

## Trading Modes

Set `TRADING_MODE` in `.env`:

| Mode | Description |
|------|-------------|
| `paper` | Simulates all orders in memory. No real money. Safe for testing. |
| `live` | Routes orders to MT5 / Binance. **Real money at risk.** |

> **Warning:** Always test in `paper` mode for at least 2–4 weeks before switching to `live`.

---

## Session Filter

Trading is restricted to **London** (07:00–16:00 UTC) and **New York** (13:00–22:00 UTC) sessions.  
The London/NY overlap (13:00–16:00 UTC) is the highest-priority window.

---

## Symbols

**Forex (MT5):** `EURUSD`, `GBPUSD`, `USDJPY`, `AUDUSD`, `USDCAD`  
**Crypto (Binance):** `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`

Configure via `FOREX_SYMBOLS` and `CRYPTO_SYMBOLS` in `.env`.

---

## Broker Setup

### MetaTrader 5
1. Open MT5 terminal and enable **Algo Trading**
2. Set `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` in `.env`
3. MT5 must run on Windows (or Wine); the Python package proxies to the terminal

### Binance
1. Create API keys with **Futures trading** permission
2. Set `BINANCE_API_KEY` and `BINANCE_API_SECRET` in `.env`
3. Set `BINANCE_TESTNET=true` for paper trading on the testnet

---

## License

MIT
