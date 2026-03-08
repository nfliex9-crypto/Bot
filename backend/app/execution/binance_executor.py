"""
Binance Execution Engine

Handles all order management for Crypto via Binance:
- Spot and Futures market orders
- Stop loss and take profit orders
- OCO (One-Cancels-the-Other) orders
- Real-time price feeds
- OHLCV data retrieval via REST API
- WebSocket price streaming
"""

import logging
import asyncio
import aiohttp
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import hmac
import hashlib
import time
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

BINANCE_BASE_URL = "https://api.binance.com"
BINANCE_TESTNET_URL = "https://testnet.binance.vision"
BINANCE_FUTURES_URL = "https://fapi.binance.com"

TIMEFRAME_MAP = {
    "M1": "1m", "M3": "3m", "M5": "5m", "M15": "15m", "M30": "30m",
    "H1": "1h", "H2": "2h", "H4": "4h", "H6": "6h", "H8": "8h", "H12": "12h",
    "D1": "1d", "W1": "1w",
}


class BinanceExecutor:
    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = True,
        simulation_mode: bool = False,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.simulation_mode = simulation_mode or not api_key
        self.base_url = BINANCE_TESTNET_URL if testnet else BINANCE_BASE_URL
        self._session: Optional[aiohttp.ClientSession] = None
        self._sim_orders: Dict[str, dict] = {}
        self._sim_order_counter = 80000

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"X-MBX-APIKEY": self.api_key}
            )
        return self._session

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        params["signature"] = signature
        return params

    async def _get(self, path: str, params: dict = None, signed: bool = False) -> Any:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        if params is None:
            params = {}
        if signed:
            params = self._sign(params)
        try:
            async with session.get(url, params=params) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"Binance GET {path} error: {e}")
            return None

    async def _post(self, path: str, params: dict) -> Any:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        params = self._sign(params)
        try:
            async with session.post(url, params=params) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"Binance POST {path} error: {e}")
            return None

    async def _delete(self, path: str, params: dict) -> Any:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        params = self._sign(params)
        try:
            async with session.delete(url, params=params) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"Binance DELETE {path} error: {e}")
            return None

    async def get_account_info(self) -> Dict:
        if self.simulation_mode:
            return {
                "balances": [
                    {"asset": "USDT", "free": "10000.00", "locked": "0.00"},
                    {"asset": "BTC", "free": "0.1", "locked": "0.00"},
                ],
                "totalBalance": 10000.0,
                "broker": "Binance Simulation",
            }

        data = await self._get("/api/v3/account", signed=True)
        if data is None:
            return {}

        return data

    async def get_current_price(self, symbol: str) -> Optional[Dict]:
        """Get latest price for a symbol."""
        if self.simulation_mode:
            base_prices = {
                "BTCUSDT": 43000.0, "ETHUSDT": 2500.0, "BNBUSDT": 300.0,
                "SOLUSDT": 100.0, "XRPUSDT": 0.55, "ADAUSDT": 0.45,
            }
            sym = symbol.upper().replace("/", "")
            base = base_prices.get(sym, 1.0)
            price = base * (1 + np.random.normal(0, 0.001))
            spread = price * 0.0005
            return {"bid": round(price - spread, 4), "ask": round(price + spread, 4), "price": round(price, 4)}

        data = await self._get("/api/v3/ticker/bookTicker", {"symbol": symbol.upper()})
        if data is None or "bidPrice" not in data:
            return None

        return {
            "bid": float(data["bidPrice"]),
            "ask": float(data["askPrice"]),
            "price": (float(data["bidPrice"]) + float(data["askPrice"])) / 2,
        }

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "H1",
        count: int = 200,
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV klines from Binance."""
        if self.simulation_mode:
            return self._generate_sim_ohlcv(symbol, count)

        interval = TIMEFRAME_MAP.get(timeframe.upper(), "1h")
        sym = symbol.upper().replace("/", "")

        data = await self._get("/api/v3/klines", {
            "symbol": sym,
            "interval": interval,
            "limit": count,
        })

        if data is None or not isinstance(data, list):
            return None

        rows = []
        for k in data:
            rows.append({
                "timestamp": pd.to_datetime(k[0], unit="ms"),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })

        return pd.DataFrame(rows)

    def _generate_sim_ohlcv(self, symbol: str, count: int = 200) -> pd.DataFrame:
        np.random.seed(hash(symbol) % 2**31)
        base_prices = {
            "BTCUSDT": 43000.0, "ETHUSDT": 2500.0, "BNBUSDT": 300.0,
            "SOLUSDT": 100.0,
        }
        sym = symbol.upper().replace("/", "")
        base = base_prices.get(sym, 100.0)
        volatility = base * 0.012

        closes = [base]
        for _ in range(count - 1):
            change = np.random.normal(0, volatility)
            closes.append(max(closes[-1] + change, base * 0.1))

        data = []
        for i, close in enumerate(closes):
            open_ = closes[i - 1] if i > 0 else close * 0.999
            high = max(open_, close) + abs(np.random.normal(0, volatility * 0.5))
            low = min(open_, close) - abs(np.random.normal(0, volatility * 0.5))
            vol = float(np.random.uniform(100, 5000))
            data.append({"open": open_, "high": high, "low": low, "close": close, "volume": vol})

        df = pd.DataFrame(data)
        df.index = pd.date_range(end=datetime.now(timezone.utc), periods=count, freq="1h")
        df.index.name = "timestamp"
        return df.reset_index()

    async def place_market_order(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        stop_loss: float,
        tp1: float,
        tp2: float,
        tp3: float,
    ) -> Dict:
        """
        Place a market order on Binance spot.
        Returns order result dict.
        """
        sym = symbol.upper().replace("/", "")

        if self.simulation_mode:
            price_info = await self.get_current_price(symbol)
            entry_price = price_info["ask"] if direction == "LONG" else price_info["bid"]
            self._sim_order_counter += 1
            order_id = str(self._sim_order_counter)

            self._sim_orders[order_id] = {
                "symbol": sym, "direction": direction,
                "quantity": quantity, "entry_price": entry_price,
                "stop_loss": stop_loss, "tp1": tp1, "tp2": tp2, "tp3": tp3,
                "status": "OPEN",
            }
            logger.info(f"[SIM] Binance order placed: {sym} {direction} {quantity} @ {entry_price}")
            return {"success": True, "order_id": order_id, "entry_price": entry_price}

        side = "BUY" if direction == "LONG" else "SELL"

        # Determine quantity precision
        qty = round(quantity, 6)

        params = {
            "symbol": sym,
            "side": side,
            "type": "MARKET",
            "quantity": qty,
        }

        result = await self._post("/api/v3/order", params)
        if result is None or "orderId" not in result:
            error = result.get("msg", "Unknown error") if result else "No response"
            return {"success": False, "error": error}

        entry_price = float(result.get("fills", [{}])[0].get("price", 0)) if result.get("fills") else 0.0

        # Place stop loss order
        await self._place_stop_loss(sym, direction, quantity, stop_loss)

        # Place TP1 limit order
        await self._place_take_profit(sym, direction, quantity * 0.5, tp1)

        return {
            "success": True,
            "order_id": str(result["orderId"]),
            "entry_price": entry_price,
        }

    async def _place_stop_loss(self, symbol: str, direction: str, quantity: float, price: float) -> Optional[Dict]:
        side = "SELL" if direction == "LONG" else "BUY"
        stop_price = round(price * 1.001, 6) if direction == "SHORT" else round(price * 0.999, 6)

        params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP_LOSS_LIMIT",
            "timeInForce": "GTC",
            "quantity": round(quantity, 6),
            "price": str(round(price, 6)),
            "stopPrice": str(stop_price),
        }
        return await self._post("/api/v3/order", params)

    async def _place_take_profit(self, symbol: str, direction: str, quantity: float, price: float) -> Optional[Dict]:
        side = "SELL" if direction == "LONG" else "BUY"
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": round(quantity, 6),
            "price": str(round(price, 6)),
        }
        return await self._post("/api/v3/order", params)

    async def cancel_order(self, symbol: str, order_id: str) -> bool:
        if self.simulation_mode:
            if order_id in self._sim_orders:
                self._sim_orders[order_id]["status"] = "CANCELLED"
            return True

        sym = symbol.upper().replace("/", "")
        result = await self._delete("/api/v3/order", {
            "symbol": sym, "orderId": int(order_id)
        })
        return result is not None and "orderId" in result

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        if self.simulation_mode:
            return [
                {**v, "order_id": k}
                for k, v in self._sim_orders.items()
                if v["status"] == "OPEN"
            ]

        params = {}
        if symbol:
            params["symbol"] = symbol.upper().replace("/", "")

        result = await self._get("/api/v3/openOrders", params, signed=True)
        return result or []

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
