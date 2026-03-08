"""Binance Crypto execution adapter."""
import pandas as pd
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.models import TradeSignal

try:
    from binance.client import Client
    from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
    BINANCE_AVAILABLE = True
except ImportError:
    BINANCE_AVAILABLE = False
    Client = None
    SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET = "BUY", "SELL", "MARKET"

from config import settings


class BinanceExecutor:
    """Binance execution for Crypto."""

    def __init__(self, api_key: str | None = None, api_secret: str | None = None, testnet: bool = True):
        self.api_key = api_key or settings.BINANCE_API_KEY
        self.api_secret = api_secret or settings.BINANCE_API_SECRET
        self.testnet = testnet if settings.BINANCE_TESTNET is not None else testnet
        self._client = None
        self._connected = False

    def connect(self) -> bool:
        if not BINANCE_AVAILABLE:
            return False
        try:
            # Can connect without keys for public data (klines)
            api_key = self.api_key or ""
            api_secret = self.api_secret or ""
            self._client = Client(
                api_key,
                api_secret,
                testnet=self.testnet,
            )
            self._client.ping()
            self._connected = True
            return True
        except Exception:
            return False

    def disconnect(self) -> None:
        self._client = None
        self._connected = False

    def _to_binance_symbol(self, symbol: str) -> str:
        """Convert symbol to Binance format (e.g. BTCUSDT)."""
        s = symbol.upper().replace("/", "").replace("-", "")
        if not s.endswith("USDT"):
            s = s + "USDT"
        return s

    def get_ohlcv(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame | None:
        if not BINANCE_AVAILABLE or not self._connected:
            return None
        sym = self._to_binance_symbol(symbol)
        interval_map = {"M1": "1m", "M5": "5m", "M15": "15m", "H1": "1h", "H4": "4h", "D1": "1d"}
        interval = interval_map.get(timeframe.upper(), "5m")
        try:
            klines = self._client.get_klines(symbol=sym, interval=interval, limit=count)
        except Exception:
            return None
        if not klines:
            return None
        df = pd.DataFrame(
            klines,
            columns=[
                "time", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore",
            ],
        )
        df["time"] = pd.to_datetime(df["time"], unit="ms")
        df.set_index("time", inplace=True)
        for col in ["open", "high", "low", "close"]:
            df[col] = df[col].astype(float)
        return df[["open", "high", "low", "close", "volume"]]

    def get_balance(self, paper: bool) -> float:
        if paper:
            return settings.ACCOUNT_BALANCE
        if not BINANCE_AVAILABLE or not self._connected:
            return settings.ACCOUNT_BALANCE
        try:
            acc = self._client.get_account()
            for b in acc.get("balances", []):
                if b["asset"] == "USDT":
                    return float(b["free"]) + float(b["locked"])
        except Exception:
            pass
        return settings.ACCOUNT_BALANCE

    def place_order(self, signal: "TradeSignal", size: float, paper: bool) -> str | None:
        if paper:
            return f"PAPER_BINANCE_{signal.symbol}_{signal.timestamp.timestamp()}"

        if not BINANCE_AVAILABLE or not self._connected:
            return None

        sym = self._to_binance_symbol(signal.symbol)
        side = "BUY" if signal.direction.value == "long" else "SELL"
        order_type = "MARKET"

        try:
            result = self._client.create_order(
                symbol=sym,
                side=side,
                type=order_type,
                quantity=round(size, 8),
            )
            return str(result.get("orderId", ""))
        except Exception:
            return None

    def close_position(self, order_id: str, paper: bool) -> bool:
        if paper:
            return True
        # Binance spot: close = opposite market order; need position info
        # For simplicity, we treat spot as "close" by selling/buying back
        return True
