# AI Automated Trading System

A full-stack AI-powered automated trading system for Forex (MetaTrader 5) and Crypto (Binance) markets.

## Architecture

```
├── backend/                  # Python FastAPI backend
│   ├── app/
│   │   ├── api/              # REST endpoints & WebSocket
│   │   ├── core/             # Config, security, logging
│   │   ├── db/               # PostgreSQL models (SQLAlchemy)
│   │   ├── market_connectors/# MT5 & Binance connectors
│   │   ├── strategy/         # SMC strategy logic
│   │   ├── risk_engine/      # Position sizing & risk management
│   │   ├── ai_layer/         # Random Forest classifier
│   │   ├── execution/        # Trade execution engine
│   │   ├── schemas/          # Pydantic schemas
│   │   └── services/         # Business logic services
│   ├── alembic/              # Database migrations
│   └── tests/                # Unit tests
├── frontend/                 # Flutter mobile app
│   └── lib/
│       ├── screens/          # Dashboard, Signals, Trades
│       ├── widgets/          # Equity, Risk, AI cards
│       ├── models/           # Data models
│       ├── services/         # API & WebSocket services
│       └── providers/        # State management
├── docker-compose.yml        # Production deployment
└── docker-compose.dev.yml    # Development environment
```

## Strategy Logic

- **Liquidity Sweep Detection** - Identifies stop hunts at swing highs/lows
- **Break of Structure (BOS)** - Detects structural shifts and Change of Character (ChoCH)
- **Pullback Entry Model** - Fibonacci retracement entries with order block confluence

## Risk Management

| Parameter | Value |
|-----------|-------|
| Risk per trade | 0.75% |
| Max drawdown | 15% |
| Trades per session | 3 |
| Stop loss | ATR-based (1.5x ATR) |
| Take profits | TP1 (1.5R), TP2 (2.5R), TP3 (4R) |
| Break-even | After TP1 hit |

## AI Layer

- Random Forest classifier trained on historical OHLCV data
- 28 technical features including RSI, MACD, Bollinger Bands, volume profile
- Trade confidence scoring combining strategy + ML predictions

## Quick Start

### Docker (Recommended)

```bash
# Clone and start
cp backend/.env.example backend/.env
# Edit .env with your API keys

docker-compose up -d --build
```

The API will be available at `http://localhost:8000` with Swagger docs at `/docs`.

### Local Development

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
flutter pub get
flutter run
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Register user |
| `/api/v1/auth/login` | POST | Login |
| `/api/v1/trading/signals` | GET | Scan markets for signals |
| `/api/v1/trading/execute` | POST | Execute a trade |
| `/api/v1/trading/trades` | GET | Trade history |
| `/api/v1/trading/dashboard` | GET | Dashboard data |
| `/api/v1/trading/risk-status` | GET | Risk management status |
| `/api/v1/ai/train` | POST | Train AI model |
| `/api/v1/ai/metrics` | GET | Model metrics |
| `/api/v1/ai/predict` | POST | Get confidence prediction |
| `/ws/dashboard` | WS | Real-time dashboard |
| `/ws/signals` | WS | Real-time signals |
| `/ws/trades` | WS | Real-time trade monitoring |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection (async) |
| `REDIS_URL` | Redis connection |
| `SECRET_KEY` | JWT secret key |
| `MT5_LOGIN` | MetaTrader 5 account number |
| `MT5_PASSWORD` | MT5 password |
| `MT5_SERVER` | MT5 broker server |
| `BINANCE_API_KEY` | Binance API key |
| `BINANCE_API_SECRET` | Binance API secret |
| `BINANCE_TESTNET` | Use Binance testnet (true/false) |
| `RISK_PER_TRADE` | Risk per trade (default: 0.0075) |
| `MAX_DRAWDOWN` | Max drawdown (default: 0.15) |
| `MAX_TRADES_PER_SESSION` | Session trade limit (default: 3) |

## Tech Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Pandas, NumPy, Scikit-learn
- **Database**: PostgreSQL
- **Cache**: Redis
- **Frontend**: Flutter (iOS/Android)
- **Deployment**: Docker, Docker Compose
