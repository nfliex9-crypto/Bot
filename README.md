# AI Automated Trading System

Production-style multi-market trading architecture with:

- **Backend**: Python, FastAPI, Pandas, NumPy, Scikit-learn
- **Markets**: Forex (MetaTrader5), Crypto (Binance API)
- **Strategy**: Liquidity sweep + break of structure + pullback entry
- **Risk engine**:
  - 0.75% risk per trade
  - 15% max drawdown lockout
  - 3 trades per session
  - ATR-based stop-loss
  - TP1/TP2/TP3 targets
  - Break-even movement after TP1
- **AI layer**: Random Forest confidence scoring
- **Database**: PostgreSQL
- **Frontend**: Flutter mobile dashboard (equity, trade history, AI confidence, live signals)
- **Deployment**: Docker + docker-compose, cloud-ready configuration

## Repository layout

```text
backend/
  app/
    ai/
    core/
    db/
    execution/
    risk/
    services/
    strategy/
    main.py
  Dockerfile
  requirements.txt
frontend_flutter/
  lib/
    models/
    screens/
    services/
    main.dart
docker-compose.yml
.env.example
```

## Backend architecture

### Strategy pipeline

1. Fetch OHLCV market data from MT5/Binance providers.
2. Detect:
   - liquidity sweep (stop-run behavior)
   - break of structure (BOS)
   - pullback entry (EMA20 pullback confirmation)
3. Build directional signal (`buy/sell/none`).

### AI confidence layer

`TradeConfidenceModel` uses a Random Forest classifier with engineered candle/volume features:

- returns: 1/3/5 bars
- candle range/body
- volume change

Model outputs confidence via `predict_proba`, and trades are blocked below threshold.

### Risk engine

`RiskEngine` enforces:

- max drawdown and session trade cap
- ATR stop-loss (`atr_multiplier`)
- position sizing from fixed risk amount
- TP ladder (TP1/TP2/TP3)
- TP1 endpoint to move SL to break-even

### Execution layer

- `MT5ExecutionEngine`: places market orders to MetaTrader5.
- `BinanceExecutionEngine`: places market orders to Binance.
- If credentials/dependencies are missing, system automatically runs in **paper mode**.

### Storage and dashboard API

PostgreSQL stores trade records. FastAPI exposes:

- `POST /api/v1/trade/run` - run one decision/execution cycle
- `GET /api/v1/trades` - trade history
- `POST /api/v1/trades/{trade_id}/tp1-hit` - mark TP1 and move to break-even
- `GET /api/v1/dashboard` - equity, history, confidence, live signal
- `GET /api/v1/metrics/equity` - equity and drawdown metrics
- `GET /api/v1/risk/config` - active risk constraints
- `GET /health` - health check
- `WS /ws/signals` - live signal feed

## Quick start (Docker)

1. Copy env:

```bash
cp .env.example .env
```

2. Start services:

```bash
docker compose up --build
```

3. Open docs:

`http://localhost:8000/docs`

## Flutter dashboard

```bash
cd frontend_flutter
flutter pub get
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

Dashboard shows:

- equity
- trade history
- AI confidence
- live signals via websocket

## Cloud-ready guidance

- Dockerized backend container
- Environment-driven config (`.env`)
- Health endpoint for probes
- Stateless API app with external PostgreSQL volume/service
- Execution adapters isolated behind service interfaces for broker-specific scaling

## Example trade cycle request

```json
{
  "market": "crypto",
  "symbol": "BTCUSDT",
  "timeframe": "M15",
  "bars": 300,
  "session_id": "london-session",
  "equity": 10000
}
```

## Notes

- Real broker execution requires valid API credentials and network access.
- Risk controls are hard constraints and enforced before order placement.
