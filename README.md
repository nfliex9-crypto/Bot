# AI Automated Trading System

A production-ready, AI-powered automated trading system for Forex (MetaTrader 5) and Crypto (Binance), with a Flutter mobile dashboard.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                     Flutter Mobile App                        │
│  Dashboard · Equity Curve · Live Signals · Trade History      │
│  AI Confidence · WebSocket Feed · Risk Stats                  │
└─────────────────────────┬────────────────────────────────────┘
                           │ HTTP / WebSocket
┌─────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend                             │
│                                                               │
│  ┌─────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │  Strategy   │  │   Risk     │  │     AI Classifier    │  │
│  │  Engine     │  │   Engine   │  │  Random Forest       │  │
│  │             │  │            │  │  30 features         │  │
│  │ ·Liq Sweep  │  │ ·0.75% risk│  │  Confidence scoring │  │
│  │ ·BOS        │  │ ·15% DD    │  │  Feature importance │  │
│  │ ·Pullback   │  │ ·3/session │  └──────────────────────┘  │
│  │ ·Fib/FVG    │  │ ·ATR SL    │                             │
│  └─────────────┘  │ ·TP1/2/3   │  ┌──────────────────────┐  │
│                   │ ·Break-even│  │  Execution Engine    │  │
│                   └────────────┘  │  · MT5 (Forex)       │  │
│                                   │  · Binance (Crypto)  │  │
│                                   └──────────────────────┘  │
└─────────────────────────┬────────────────────────────────────┘
                           │
                  ┌────────▼────────┐
                  │   PostgreSQL    │
                  │  Trades·Signals │
                  │  Accounts·Equity│
                  └─────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.11, FastAPI, SQLAlchemy (async), APScheduler |
| Strategy | Pandas, NumPy, custom ICT/SMC logic |
| AI Model | Scikit-learn Random Forest, 30 engineered features |
| Forex Broker | MetaTrader 5 Python API |
| Crypto Broker | Binance REST + WebSocket API |
| Database | PostgreSQL 15 |
| Frontend | Flutter 3 (mobile + web), Provider, fl_chart |
| Infrastructure | Docker Compose, Nginx |

---

## Quick Start

### Prerequisites
- Docker Desktop / Docker Engine + Compose
- (Optional) Binance account + API keys for crypto trading
- (Optional) MT5 Windows VPS for Forex execution

### 1. Clone and configure

```bash
git clone <repo>
cd ai-trading-system
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start all services

```bash
docker compose up -d
```

Services started:
- `http://localhost:8000` — Backend API
- `http://localhost:8000/docs` — Interactive API docs (Swagger)
- `http://localhost:80` — Nginx reverse proxy
- `ws://localhost:8000/ws` — WebSocket live feed
- `http://localhost:5432` — PostgreSQL

### 3. View API docs

Open `http://localhost:8000/docs` to explore all REST endpoints.

### 4. Run Flutter App (Mobile)

```bash
cd frontend
flutter pub get
flutter run
# For web:
flutter run -d chrome --dart-define=API_BASE_URL=http://localhost:8000
```

---

## Strategy Logic

### 1. Liquidity Sweep Detection
Price briefly breaks above a swing high (bearish setup) or below a swing low (bullish setup), then closes back inside. Identifies stop-hunt zones used by institutional traders.

**Parameters:**
- Lookback: 20 bars for swing identification
- Rejection ratio: ≥ 0.6 wick-to-body
- ATR buffer: 0.3× ATR for valid pierce

### 2. Break of Structure (BOS)
After a sweep, confirms market direction shift by breaking a structural swing level with a full-body candle ≥ 0.8× ATR.

- Bullish BOS → confirms LONG bias
- Bearish BOS → confirms SHORT bias

### 3. Pullback Entry Model
Waits for price to retrace into the 50%-61.8% Fibonacci zone before entry. Adds confluence from:
- **Order Blocks** (last opposite-direction candle pre-impulse)
- **Fair Value Gaps** (3-candle price imbalance)
- **RSI** (avoids buying overbought / selling oversold)

---

## Risk Engine

| Parameter | Value |
|---|---|
| Risk per trade | 0.75% of account |
| Max drawdown | 15% (trading halts) |
| Max trades/session | 3 |
| Stop Loss | ATR-based (1.0× ATR buffer beyond sweep) |
| TP1 | 1.5 × SL distance |
| TP2 | 2.5 × SL distance |
| TP3 | 4.0 × SL distance |
| Break-even | Triggered when TP1 is hit |

**Lot size** is calculated automatically: `lot_size = (balance × 0.0075) / (SL_pips × pip_value)`

---

## AI Model

**Random Forest Classifier** trained to predict trade outcomes (win/loss).

### Feature Categories (30 total)
- **RSI**: 7-period and 14-period
- **EMA relationships**: 8/21/50 EMA vs price and vs each other
- **MACD**: normalised line and histogram
- **Bollinger Bands**: width and position
- **ATR**: normalised volatility
- **Volume**: ratio vs 20-bar average, trend
- **Price action**: body ratios, wick ratios, candle size
- **Momentum**: 1/3/5-bar momentum
- **Volatility regime**: current ATR vs 20-bar average
- **Signal context**: setup quality, RSI, FVG, order block, R:R

Confidence score ≥ 65% required before executing a trade.

### Retraining

The model bootstraps on synthetic data at startup. To retrain on real trade history:

```bash
curl -X POST http://localhost:8000/api/v1/ai/model/retrain
```

---

## API Reference

### Trades
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/trades/` | List all trades |
| GET | `/api/v1/trades/open` | Open positions |
| GET | `/api/v1/trades/stats` | Win rate, P&L, stats |
| GET | `/api/v1/trades/{id}` | Single trade |
| PATCH | `/api/v1/trades/{id}` | Update trade |

### Signals
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/signals/` | All signals |
| GET | `/api/v1/signals/active` | Active signals |
| GET | `/api/v1/signals/{id}` | Single signal |

### Account
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/account/summary` | Equity + stats |
| GET | `/api/v1/account/equity-curve` | Historical equity |

### AI
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/ai/model/info` | Model metadata |
| POST | `/api/v1/ai/model/retrain` | Retrain on history |
| GET | `/api/v1/ai/confidence/history` | Past confidence scores |

### WebSocket
Connect to `ws://localhost:8000/ws` for real-time events:

```json
// Incoming signal event
{
  "type": "signal",
  "data": {
    "symbol": "EURUSD",
    "direction": "LONG",
    "confidence_score": 0.78,
    "entry_price": 1.08500,
    "stop_loss": 1.08100,
    "tp1": 1.09100,
    "tp2": 1.09500,
    "tp3": 1.10100,
    ...
  }
}
```

---

## Project Structure

```
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + scheduler
│   │   ├── config.py            # Settings (env-based)
│   │   ├── database.py          # Async SQLAlchemy engine
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── trade.py
│   │   │   ├── signal.py
│   │   │   └── account.py
│   │   ├── schemas/             # Pydantic v2 schemas
│   │   ├── api/v1/              # REST + WebSocket routes
│   │   │   ├── trades.py
│   │   │   ├── signals.py
│   │   │   ├── account.py
│   │   │   ├── ai.py
│   │   │   └── websocket.py
│   │   ├── strategy/            # Trading strategy logic
│   │   │   ├── liquidity_sweep.py
│   │   │   ├── break_of_structure.py
│   │   │   ├── pullback_entry.py
│   │   │   └── signal_generator.py
│   │   ├── risk/
│   │   │   └── engine.py        # Position sizing, drawdown
│   │   ├── ai/
│   │   │   ├── classifier.py    # Random Forest model
│   │   │   └── features.py      # Feature engineering
│   │   ├── execution/
│   │   │   ├── mt5_executor.py  # MetaTrader5 orders
│   │   │   └── binance_executor.py
│   │   └── services/
│   │       ├── market_data.py
│   │       └── trade_manager.py # Orchestration layer
│   ├── alembic/                 # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                    # Flutter mobile app
│   ├── lib/
│   │   ├── main.dart
│   │   ├── config/app_config.dart
│   │   ├── models/              # trade.dart, signal.dart, account.dart
│   │   ├── services/            # api_service.dart, websocket_service.dart
│   │   ├── providers/           # trading_provider.dart
│   │   ├── screens/             # dashboard, trades, signals, settings
│   │   └── widgets/             # equity_chart, signal_card, trade_card, confidence_meter
│   ├── pubspec.yaml
│   └── Dockerfile
│
├── nginx/nginx.conf             # Reverse proxy config
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## MT5 Notes

MetaTrader 5's Python library (`MetaTrader5`) only runs on **Windows**. On Linux/Mac/Docker, the MT5 executor automatically switches to **simulation mode**, generating realistic synthetic OHLCV data and logging mock orders.

For live Forex trading, deploy the backend on a **Windows VPS** with MT5 installed, or use a bridge service.

---

## Binance Setup

1. Log in to Binance → API Management → Create API Key
2. Enable **Enable Reading** and **Enable Spot & Margin Trading**
3. Set `BINANCE_TESTNET=false` in `.env` for live trading
4. Add IP whitelist for your server IP (recommended)

---

## Cloud Deployment (AWS/GCP/DigitalOcean)

```bash
# 1. Push to your VPS
scp -r . user@your-server:/opt/ai-trading

# 2. Configure environment
ssh user@your-server
cd /opt/ai-trading
cp .env.example .env
vim .env   # Add your real keys

# 3. Start
docker compose up -d

# 4. Set up SSL (Let's Encrypt)
certbot --nginx -d your-domain.com
```

For auto-scaling, the backend is stateless (AI model stored in a Docker volume) and can run multiple replicas behind a load balancer.

---

## Development

```bash
# Backend (local dev)
cd backend
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# Run tests
pytest

# Flutter (mobile dev)
cd frontend
flutter pub get
flutter run
```

---

## Disclaimer

This system is provided for **educational and research purposes only**. Automated trading carries significant financial risk. Past performance of any strategy does not guarantee future results. Always test thoroughly in simulation/paper trading mode before deploying with real capital. The authors assume no responsibility for financial losses.
