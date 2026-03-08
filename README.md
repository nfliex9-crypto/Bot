# AI Trading Bot

Automated trading system for **Forex** (MetaTrader 5) and **Crypto** (Binance) markets, powered by Smart Money Concepts (SMC) strategy and a RandomForest AI classifier.

## Architecture

```
main.py                    Entry point — FastAPI + bot loop
bot.py                     Main orchestrator — scan/manage/snapshot loops
├── config/settings.py     Central configuration (env vars)
├── core/
│   ├── models.py          Data models (Trade, Signal, AccountState, etc.)
│   └── logger.py          Structured logging
├── data/
│   ├── mt5_provider.py    MetaTrader 5 candle + tick data
│   └── binance_provider.py Binance REST market data
├── strategy/
│   ├── smc_strategy.py    Multi-timeframe SMC strategy engine
│   ├── structure.py       Swing points, BOS, CHoCH detection
│   ├── liquidity.py       Liquidity sweep detection
│   └── indicators.py      ATR, RSI, EMA, MACD, VWAP, Bollinger, etc.
├── risk/
│   └── risk_manager.py    Position sizing, drawdown, daily limits
├── trade_management/
│   └── manager.py         Multi-TP, break-even, partial close logic
├── ai/
│   ├── classifier.py      RandomForest trade classifier
│   └── feature_engine.py  40+ feature extraction from MTF data
├── filters/
│   ├── session_filter.py  London + New York session filter
│   └── news_filter.py     High-impact news avoidance
├── execution/
│   ├── mt5_executor.py    MT5 order execution
│   ├── binance_executor.py Binance order execution
│   └── paper_executor.py  Simulated fills for paper mode
├── database/
│   ├── models.py          SQLAlchemy ORM (trades, signals, snapshots)
│   └── repository.py      CRUD operations
├── api/
│   ├── app.py             FastAPI application factory
│   └── routes.py          REST API endpoints
└── tests/                 47 unit tests
```

## Strategy

**Smart Money Concepts (SMC) with multi-timeframe confluence:**

| Timeframe | Purpose |
|-----------|---------|
| H1 | Market bias — bullish/bearish/neutral |
| M15 | Trend structure — Break of Structure (BOS) confirmation |
| M5 | Execution — liquidity sweep + pullback entry |

**Signal flow:**
1. H1 determines directional bias (HH/HL = bullish, LL/LH = bearish)
2. M15 confirms with Break of Structure in the same direction
3. M5 detects a liquidity sweep into a pullback zone (order block or swing)
4. AI classifier scores the signal
5. Risk manager validates position sizing and limits
6. Order executed via MT5, Binance, or paper engine

## Risk Management

| Parameter | Value |
|-----------|-------|
| Account Balance | $3,000 |
| Risk per Trade | 0.75% ($22.50) |
| Max Drawdown | 15% |
| Max Trades/Session | 3 |
| Max Daily Loss | 5% |

**Trade management:**
- Stop loss: ATR-based with structure confirmation
- TP1 = 1R → close 40%, move SL to break-even
- TP2 = 1.5R → close 30%
- TP3 = 2R → close remaining 30%

## Quick Start

### Docker (recommended)

```bash
cp .env.example .env
# Edit .env with your API keys and settings
docker compose up -d
```

The bot starts at `http://localhost:8000`. API docs at `/docs`.

### Local

```bash
pip install -r requirements.txt

# Paper mode (default)
export TRADING_MODE=paper
python main.py

# Or use the scripts
./scripts/run_paper.sh
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/status` | Bot status, mode, uptime, risk summary |
| GET | `/api/v1/trades` | Recent trade history |
| GET | `/api/v1/trades/open` | Currently open positions |
| GET | `/api/v1/account` | Account balance and stats |
| GET | `/api/v1/account/history` | Equity curve data |
| GET | `/api/v1/signals/recent` | Recent signals (executed + rejected) |
| POST | `/api/v1/mode` | Switch paper/live `{"mode": "paper"}` |
| POST | `/api/v1/bot/start` | Start scanning |
| POST | `/api/v1/bot/stop` | Stop scanning |
| POST | `/api/v1/ml/retrain` | Retrain the AI model |
| GET | `/api/v1/ml/status` | ML model status |

## Configuration

All settings via environment variables (see `.env.example`):

- `TRADING_MODE` — `paper` or `live`
- `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER` — MetaTrader 5 credentials
- `BINANCE_API_KEY`, `BINANCE_API_SECRET` — Binance credentials
- `BINANCE_TESTNET` — `true` for testnet, `false` for live
- `ACCOUNT_BALANCE` — Starting balance for risk calculations
- `MIN_CONFIDENCE` — Minimum signal confidence threshold (0.65 default)

## AI Layer

- **Model:** RandomForest classifier (100 trees, balanced classes)
- **Features:** 40+ features from 3 timeframes (price, momentum, volatility, volume, structure)
- **Training:** Learns incrementally from trade outcomes
- **Scoring:** Blends strategy confidence (60%) with ML prediction (40%)
- **Retrain:** `POST /api/v1/ml/retrain` or `python scripts/retrain_model.py`

## Testing

```bash
pip install pytest pytest-asyncio
python -m pytest tests/ -v
```

## Filters

- **Session filter:** Only trades during London (08:00–16:00 UTC) and New York (13:00–21:00 UTC)
- **News filter:** Blocks trading 30 minutes before/after high-impact news events

## Safety Notes

- Always start in `paper` mode to validate strategy
- The bot respects all risk limits — max drawdown will halt trading
- Live mode requires valid broker credentials
- Monitor via the API dashboard at `http://localhost:8000/docs`
