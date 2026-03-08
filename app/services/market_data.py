from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.config import Settings
from app.domain.models import Market, MarketSnapshot
from app.services.indicators import normalize_dataframe

TIMEFRAME_MAP_BINANCE = {
    "H1": "1h",
    "M15": "15m",
    "M5": "5m",
}


class BaseMarketDataProvider(ABC):
    @abstractmethod
    def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        raise NotImplementedError

    @abstractmethod
    def current_price(self, symbol: str) -> float:
        raise NotImplementedError


class BinanceMarketDataProvider(BaseMarketDataProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = "https://fapi.binance.com" if settings.binance_futures else "https://api.binance.com"

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
    def _get_klines(self, symbol: str, interval: str) -> pd.DataFrame:
        endpoint = "/fapi/v1/klines" if self.settings.binance_futures else "/api/v3/klines"
        response = httpx.get(
            f"{self.base_url}{endpoint}",
            params={
                "symbol": symbol,
                "interval": TIMEFRAME_MAP_BINANCE[interval],
                "limit": self.settings.candle_limit,
            },
            timeout=20.0,
        )
        response.raise_for_status()
        rows = response.json()

        records = [
            {
                "timestamp": datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            }
            for row in rows
        ]
        return normalize_dataframe(records)

    def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        h1 = self._get_klines(symbol, "H1")
        m15 = self._get_klines(symbol, "M15")
        m5 = self._get_klines(symbol, "M5")
        return MarketSnapshot(
            market=Market.CRYPTO,
            symbol=symbol,
            h1=h1,
            m15=m15,
            m5=m5,
            current_price=float(m5["close"].iloc[-1]),
            timestamp=datetime.now(timezone.utc),
        )

    def current_price(self, symbol: str) -> float:
        endpoint = "/fapi/v1/ticker/price" if self.settings.binance_futures else "/api/v3/ticker/price"
        response = httpx.get(
            f"{self.base_url}{endpoint}",
            params={"symbol": symbol},
            timeout=10.0,
        )
        response.raise_for_status()
        ticker = response.json()
        return float(ticker["price"])


class MT5MarketDataProvider(BaseMarketDataProvider):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._mt5 = None

    def _connect_direct(self) -> object:
        if self._mt5 is not None:
            return self._mt5

        try:
            import MetaTrader5 as mt5
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise RuntimeError(
                "MetaTrader5 direct mode is unavailable; use the mt5 optional dependency or bridge mode."
            ) from exc

        initialized = mt5.initialize(
            path=self.settings.mt5_path,
            login=self.settings.mt5_login,
            server=self.settings.mt5_server,
            password=self.settings.mt5_password,
        )
        if not initialized:
            raise RuntimeError("MetaTrader5 initialize() failed")
        self._mt5 = mt5
        return mt5

    def _fetch_bridge_rates(self, symbol: str, timeframe: str) -> pd.DataFrame:
        if not self.settings.mt5_bridge_url:
            raise RuntimeError("MT5 bridge URL is required for bridge mode")
        response = httpx.get(
            f"{self.settings.mt5_bridge_url.rstrip('/')}/rates",
            params={"symbol": symbol, "timeframe": timeframe, "limit": self.settings.candle_limit},
            timeout=20.0,
        )
        response.raise_for_status()
        return normalize_dataframe(response.json())

    def _fetch_direct_rates(self, symbol: str, timeframe: str) -> pd.DataFrame:
        mt5 = self._connect_direct()
        timeframe_map = {"H1": mt5.TIMEFRAME_H1, "M15": mt5.TIMEFRAME_M15, "M5": mt5.TIMEFRAME_M5}
        rows = mt5.copy_rates_from_pos(symbol, timeframe_map[timeframe], 0, self.settings.candle_limit)
        if rows is None:
            raise RuntimeError(f"Failed to load MT5 rates for {symbol} {timeframe}")
        records = [
            {
                "timestamp": datetime.fromtimestamp(int(row["time"]), tz=timezone.utc),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["tick_volume"],
            }
            for row in rows
        ]
        return normalize_dataframe(records)

    def _get_rates(self, symbol: str, timeframe: str) -> pd.DataFrame:
        if self.settings.mt5_connection_mode == "direct":
            return self._fetch_direct_rates(symbol, timeframe)
        return self._fetch_bridge_rates(symbol, timeframe)

    def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        h1 = self._get_rates(symbol, "H1")
        m15 = self._get_rates(symbol, "M15")
        m5 = self._get_rates(symbol, "M5")
        return MarketSnapshot(
            market=Market.FOREX,
            symbol=symbol,
            h1=h1,
            m15=m15,
            m5=m5,
            current_price=float(m5["close"].iloc[-1]),
            timestamp=datetime.now(timezone.utc),
        )

    def current_price(self, symbol: str) -> float:
        if self.settings.mt5_connection_mode == "direct":
            mt5 = self._connect_direct()
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                raise RuntimeError(f"Could not fetch MT5 tick for {symbol}")
            return float(tick.bid if tick.bid else tick.ask)

        if not self.settings.mt5_bridge_url:
            raise RuntimeError("MT5 bridge URL is required for bridge mode")
        response = httpx.get(
            f"{self.settings.mt5_bridge_url.rstrip('/')}/price",
            params={"symbol": symbol},
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        return float(payload["price"])
