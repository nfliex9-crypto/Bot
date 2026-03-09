# AI Trading Platform — Code Review Package

## Overview

This document describes the full architecture, strategy logic, AI pipeline, risk management system, and deployment instructions for the AI Trading Platform.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI REST API (port 8000)                 │
│                                                                     │
│  /api/v1/bot/*      Bot control (start/stop/pause/resume)           │
│  /api/v1/trades/*   Trade history + open positions                  │
│  /api/v1/signals/*  Signal feed with AI confidence scores           │
│  /api/v1/dashboard  Equity curve, sessions, symbols, AI scores      │
│  /api/v1/monitoring Health, metrics, performance tracker            │
│  /api/v1/backtesting Run historical simulations                     │
│  /api/v1/training   Train, evaluate, hot-swap AI model              │
│  /metrics           Prometheus scrape endpoint                      │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │
┌──────────────────────────────────────▼──────────────────────────────┐
│                         Trading Bot Engine                          │
│                                                                     │
│  Scanner (every 60s)                                                │
│    → For each symbol: fetch H1/M15/M5 OHLCV                        │
│    → MTF Analysis → AI Score → Filter → Execute                     │
│                                                                     │
│  Position Monitor (every 10s)                                       │
│    → Fetch tick → Check TP/SL/BE → Update DB → Manage orders        │
│                                                                     │
│  Heartbeat (every 30s)                                              │
│    → Log uptime, P&L, error count                                   │
└──┬──────────────┬──────────────┬──────────────┬────────────────────┘
   │              │              │              │
   ▼              ▼              ▼              ▼
MT5 Broker    Binance        PostgreSQL     Risk Guards
(Forex)       (Crypto)       (Trades/       (Spread/Slip/
                             Signals/DB)    Latency/DD/Cool)
```

### Module Map

| Path | Responsibility |
|------|----------------|
| `app/bot/trading_bot.py` | Main orchestrator, task loops |
| `app/bot/scanner.py` | Multi-symbol parallel scanner |
| `app/core/strategy/` | Liquidity Sweep + BOS + Pullback |
| `app/core/strategy/multi_timeframe.py` | H1/M15/M5 analysis coordinator |
| `app/core/ai/classifier.py` | RandomForest trade classifier |
| `app/core/ai/model_registry.py` | Model versioning + hot-swap |
| `app/core/risk_manager.py` | Position sizing, drawdown tracking |
| `app/core/risk_guards.py` | Spread/slippage/latency/cooldown guards |
| `app/core/trade_manager.py` | TP/SL/break-even lifecycle |
| `app/core/session_filter.py` | London / New York session gating |
| `app/core/news_filter.py` | High-impact news blocking |
| `app/monitoring/metrics.py` | Prometheus + in-memory metrics |
| `app/monitoring/healthcheck.py` | Component health probes |
| `app/monitoring/performance_tracker.py` | Sharpe, Sortino, PF, drawdown |
| `app/backtesting/engine.py` | Bar-by-bar backtest runner |
| `app/backtesting/simulator.py` | Spread + slippage simulation |
| `app/backtesting/metrics.py` | Backtest performance metrics |
| `app/training/dataset_builder.py` | Feature collection + labelling |
| `app/training/trainer.py` | RF training + calibration pipeline |
| `app/training/evaluator.py` | Model evaluation + threshold analysis |
| `app/brokers/mt5_broker.py` | MetaTrader 5 connector |
| `app/brokers/binance_broker.py` | Binance Spot/Futures connector |
| `app/utils/logging_config.py` | Structured logging (loguru + JSON) |
| `app/utils/indicators.py` | ATR, RSI, MACD, EMA, FVG, OB |

---

## Trading Strategy: Smart Money Concepts (SMC)

### Philosophy
The strategy follows the Smart Money Concepts (SMC) framework, which assumes large institutional participants ("smart money") manipulate retail stop-losses before reversing.

### Three-Phase Setup

```
Phase 1: LIQUIDITY SWEEP (Manipulation)
  ┌─────────────────────────────────────────┐
  │  Price hunts above equal highs (BSL)    │
  │  or below equal lows (SSL)              │
  │  → Wick through the level               │
  │  → Candle closes BACK past the level    │
  │  → Rejection strength ≥ 0.3             │
  └─────────────────────────────────────────┘
                    ↓
Phase 2: BREAK OF STRUCTURE (Confirmation)
  ┌─────────────────────────────────────────┐
  │  After bullish sweep (lows taken):      │
  │    Price closes above last swing high   │
  │  After bearish sweep (highs taken):     │
  │    Price closes below last swing low    │
  │  Classifies as CHoCH (weak) or BOS      │
  └─────────────────────────────────────────┘
                    ↓
Phase 3: PULLBACK ENTRY (Execution)
  ┌─────────────────────────────────────────┐
  │  Enter on retracement into:             │
  │    1. FVG (Fair Value Gap) — priority   │
  │    2. Order Block (OB)                  │
  │    3. 50% retracement of impulse        │
  │    4. BOS level (S/R flip)              │
  │  Stop: below sweep wick (structure)     │
  │      or entry ± 1.5 × ATR              │
  └─────────────────────────────────────────┘
```

### Multi-Timeframe Analysis

| Timeframe | Role | Key Check |
|-----------|------|-----------|
| H1 | Market bias | EMA 21/50/200 + HH/HL vs LH/LL structure |
| M15 | Trend confirmation | EMA 9/21 alignment + sweep/BOS scan |
| M5 | Execution | Sweep + BOS + pullback entry detection |

A trade is only taken when all three timeframes are aligned.

### Trade Management

```
Entry         TP1 (1R)      TP2 (1.5R)   TP3 (2R)
  │───────────────┬──────────────┬────────────┤
  │               │              │            │
  SL              └─ Close 33%   └─ Close 33% └─ Close 34%
                    Move SL → BE
```

---

## AI Model Pipeline

### Feature Engineering (40 features)

| Category | Features |
|----------|----------|
| Price vs EMA | close_vs_ema9, close_vs_ema21, close_vs_ema50 |
| EMA structure | ema9_vs_ema21, ema21_vs_ema50 |
| Momentum | rsi, rsi_oversold, rsi_overbought, macd_hist, macd_signal_cross |
| Volatility | atr_pct, bb_width, close_vs_bb_upper/lower |
| Candle structure | body_ratio, upper_wick_ratio, lower_wick_ratio, is_bullish_candle |
| Sweep | sweep_detected, sweep_direction, sweep_rejection_strength, sweep_bars_ago |
| BOS | bos_detected, bos_direction, bos_strength, bos_bars_after_sweep |
| MTF | h1_bias, m15_trend, mtf_aligned, alignment_score |
| Entry zone | entry_zone_fvg, entry_zone_ob, entry_zone_50pct, risk_reward |
| Session | is_london, is_new_york, is_overlap |
| Volume | volume_ratio, swing_high_dist, swing_low_dist |

### Training Pipeline

```
1. DatasetBuilder
   ├── from_database(days=180)    ← closed trades with known outcomes
   ├── generate_synthetic(n)      ← bootstrapping when data < min_samples
   └── merge() + shuffle()

2. ModelTrainer
   ├── StandardScaler (feature normalisation)
   ├── SMOTE (class imbalance oversampling)
   ├── RandomForestClassifier (n=300, max_depth=12)
   ├── CalibratedClassifierCV (Platt scaling)
   └── joblib.dump → ai/models/trading_model.joblib

3. ModelEvaluator
   ├── ROC-AUC, PR-AUC
   ├── Calibration curve (reliability diagram)
   ├── Threshold sensitivity table
   └── Feature importance ranking

4. ModelRegistry (hot-swap)
   ├── Loads model on startup
   ├── Background file-watcher (60s poll)
   └── Atomic swap via threading.RLock
```

### Confidence Scoring

The classifier outputs a probability (0–1) of the trade being profitable.
- Default threshold: **0.65**
- Configurable via `MIN_CONFIDENCE` env var
- Falls back to heuristic rule-based scoring when no model is loaded

---

## Risk Management

### Position Sizing (Fixed Fractional)

```
risk_amount = account_balance × 0.0075        (0.75%)
pip_risk    = |entry - stop_loss| / pip_size
lot_size    = risk_amount / (pip_risk × pip_value_per_lot)
```

### Risk Guards (Execution-Time Protections)

| Guard | Trigger | Action |
|-------|---------|--------|
| `SpreadFilter` | Spread > 3 pips OR > 30% of ATR | Block order |
| `SlippageGuard` | Slippage > 2 pips | Log warning; > 5 pips → close immediately |
| `LatencyGuard` | Signal age > 1000ms | Abort order (stale price) |
| `DrawdownStop` | Drawdown ≥ 15% OR daily loss ≥ 5% | Circuit breaker |
| `TradeCooldown` | < 15 min since last trade | Defer; 30 min after a loss |

### Limits

| Parameter | Value |
|-----------|-------|
| Risk per trade | 0.75% |
| Max drawdown | 15% (hard stop) |
| Daily loss limit | 5% |
| Max trades per session | 3 |
| Min AI confidence | 0.65 |

---

## Monitoring System

### Prometheus Metrics

| Metric | Type | Description |
|--------|------|-------------|
| `trading_bot_trades_total` | Counter | Trades placed by symbol/direction |
| `trading_bot_trades_closed_total` | Counter | Closed trades by outcome |
| `trading_bot_pnl_total` | Gauge | Cumulative P&L |
| `trading_bot_drawdown_current` | Gauge | Live drawdown fraction |
| `trading_bot_win_rate` | Gauge | Running win rate |
| `trading_bot_profit_factor` | Gauge | Running profit factor |
| `trading_bot_ai_confidence` | Histogram | Confidence distribution |
| `trading_bot_trade_latency_seconds` | Histogram | Order fill latency |
| `trading_bot_slippage_pips` | Histogram | Execution slippage |
| `trading_bot_spread_pips` | Histogram | Entry spread |
| `http_requests_total` | Counter | API request count |
| `http_request_duration_seconds` | Histogram | API latency |

### Performance Metrics (PerformanceTracker)

- Win rate, profit factor, expectancy
- Max drawdown (absolute + %)
- Sharpe ratio, Sortino ratio, Calmar ratio
- Max consecutive wins/losses
- Trade duration statistics
- Breakdown: by symbol, direction, session

### Logs

| File | Content |
|------|---------|
| `logs/trading.log` | All INFO+ events (rotating daily) |
| `logs/errors.log` | ERROR+ events (rotating weekly) |
| `logs/trades.log` | Trade execution events |
| `logs/ai.log` | Model predictions + training events |

---

## Backtesting Engine

### Features
- **No lookahead bias**: strict bar-by-bar slicing
- **Variable spread**: scales with ATR-based volatility
- **Slippage**: random within ATR × slippage_factor
- **Commission**: configurable per-lot round-trip cost
- **Gap simulation**: price gaps on SL (weekend/news)
- **Full trade lifecycle**: partial closes at TP1/TP2/TP3 + break-even

### Output Metrics
Win rate, profit factor, max drawdown, Sharpe, Sortino, Calmar,
expectancy, MAE, MFE, avg slippage, trade duration, exit distribution.

---

## Deployment

### Quick Start (Paper Trading)

```bash
# 1. Configure
cp .env.example .env
# Edit .env: set TRADING_MODE=paper

# 2. Start
docker-compose up -d

# 3. Verify
curl http://localhost:8000/health
# → {"status":"healthy","mode":"paper"}

# 4. API docs
open http://localhost:8000/docs
```

### Services

| Service | Port | Purpose |
|---------|------|---------|
| `trading-bot` | 8000 | FastAPI app + trading engine |
| `postgres` | 5432 | Trade / signal persistence |
| `redis` | 6379 | Caching / pub-sub |
| `prometheus` | 9090 | Metrics scraping (profile: monitoring) |
| `grafana` | 3000 | Dashboards (profile: monitoring) |

### With Monitoring Stack

```bash
docker-compose --profile monitoring up -d
```

### Live Trading

```bash
# .env additions
TRADING_MODE=live
MT5_LOGIN=12345678
MT5_PASSWORD=your_password
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret
BINANCE_TESTNET=false
```

> **Note**: MT5 Python library requires Windows. On Linux, MT5 runs in paper mode automatically. Binance works on all platforms.

### Training the Model

```bash
# Bootstrap with synthetic data
python scripts/train_model.py --synthetic --n-synthetic 2000

# Train on real trade history (after 30+ days of paper trading)
python scripts/train_model.py --days 90

# Or via API (triggers background training)
curl -X POST http://localhost:8000/api/v1/training/train \
  -H "Content-Type: application/json" \
  -d '{"days_history": 90, "synthetic_samples": 500}'
```

---

## Security Notes

- Never commit `.env` (contains API keys)
- MT5 credentials are injected via environment variables
- Binance testnet is **enabled by default** — set `BINANCE_TESTNET=false` for live
- The circuit breaker halts all trading at 15% drawdown

---

## File Reference

```
trading-platform/
├── app/
│   ├── main.py                    FastAPI app entry point
│   ├── config.py                  Pydantic settings (env vars)
│   ├── database.py                Async PostgreSQL (asyncpg)
│   ├── models/                    SQLAlchemy ORM models
│   ├── schemas/                   Pydantic request/response schemas
│   ├── api/routes/                FastAPI route handlers
│   │   ├── control.py             Bot start/stop/pause/resume
│   │   ├── trades.py              Trade history + stats
│   │   ├── signals.py             Signal feed
│   │   ├── performance.py         Equity curve, summary
│   │   ├── dashboard.py           Frontend dashboard data
│   │   ├── monitoring.py          Health + metrics
│   │   ├── backtesting.py         Run backtests via API
│   │   └── training.py            Train + hot-swap model
│   ├── bot/
│   │   ├── trading_bot.py         Main orchestrator
│   │   └── scanner.py             Multi-symbol scanner
│   ├── brokers/
│   │   ├── base.py                Abstract broker interface
│   │   ├── mt5_broker.py          MetaTrader 5
│   │   └── binance_broker.py      Binance Spot/Futures
│   ├── core/
│   │   ├── strategy/
│   │   │   ├── liquidity_sweep.py  Sweep detection
│   │   │   ├── break_of_structure.py BOS/CHoCH detection
│   │   │   ├── pullback_entry.py   Entry zone + SL/TP calc
│   │   │   └── multi_timeframe.py  H1/M15/M5 coordinator
│   │   ├── ai/
│   │   │   ├── classifier.py       RandomForest classifier
│   │   │   ├── features.py         Feature engineering
│   │   │   └── model_registry.py   Hot-swap model registry
│   │   ├── risk_manager.py         Position sizing + drawdown
│   │   ├── risk_guards.py          Spread/slip/latency/cooldown
│   │   ├── trade_manager.py        TP/SL/BE lifecycle
│   │   ├── session_filter.py       London/NY session gate
│   │   └── news_filter.py          News event blocking
│   ├── monitoring/
│   │   ├── metrics.py              Prometheus + in-memory stats
│   │   ├── healthcheck.py          Component health probes
│   │   └── performance_tracker.py  Sharpe/Sortino/PF/DD
│   ├── backtesting/
│   │   ├── engine.py               Bar-by-bar backtest engine
│   │   ├── simulator.py            Market execution simulator
│   │   └── metrics.py              Backtest performance metrics
│   ├── training/
│   │   ├── dataset_builder.py      Feature collection + labelling
│   │   ├── trainer.py              RF training + calibration
│   │   └── evaluator.py            Model evaluation
│   └── utils/
│       ├── logging_config.py       Centralized structured logging
│       ├── logger.py               Compatibility shim
│       └── indicators.py           ATR/RSI/MACD/FVG/OB
├── scripts/
│   ├── train_model.py              CLI model training
│   └── backtest.py                 CLI backtesting
├── alembic/                        Database migrations
├── monitoring/
│   └── prometheus.yml              Prometheus scrape config
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── .env.example
```
