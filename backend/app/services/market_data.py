from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

import httpx
import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.db.models import MarketType

logger = logging.getLogger(__name__)
settings = get_settings()

try:
    import MetaTrader5 as mt5  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    mt5 = None


class MarketDataService:
    BINANCE_INTERVAL_MAP = {
        "M1": "1m",
        "M5": "5m",
        "M15": "15m",
        "M30": "30m",
        "H1": "1h",
        "H4": "4h",
        "D1": "1d",
    }

    MT5_TIMEFRAME_MAP = {
        "M1": getattr(mt5, "TIMEFRAME_M1", None),
        "M5": getattr(mt5, "TIMEFRAME_M5", None),
        "M15": getattr(mt5, "TIMEFRAME_M15", None),
        "M30": getattr(mt5, "TIMEFRAME_M30", None),
        "H1": getattr(mt5, "TIMEFRAME_H1", None),
        "H4": getattr(mt5, "TIMEFRAME_H4", None),
        "D1": getattr(mt5, "TIMEFRAME_D1", None),
    }

    def get_ohlcv(self, symbol: str, market: MarketType, timeframe: str, limit: int) -> pd.DataFrame:
        if market == MarketType.CRYPTO:
            df = self._fetch_binance_klines(symbol, timeframe, limit)
            if not df.empty:
                return df
        elif market == MarketType.FOREX:
            df = self._fetch_mt5_rates(symbol, timeframe, limit)
            if not df.empty:
                return df

        logger.warning("Falling back to synthetic market data for %s/%s", market.value, symbol)
        return self._generate_synthetic_ohlcv(symbol=symbol, limit=limit)

    def _fetch_binance_klines(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        interval = self.BINANCE_INTERVAL_MAP.get(timeframe, "15m")
        url = f"{settings.binance_base_url.rstrip('/')}/api/v3/klines"
        try:
            response = httpx.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=10.0)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # pragma: no cover - network failures are environment-specific
            logger.warning("Binance data request failed for %s: %s", symbol, exc)
            return pd.DataFrame()

        frame = pd.DataFrame(
            payload,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "number_of_trades",
                "taker_buy_base_asset_volume",
                "taker_buy_quote_asset_volume",
                "ignore",
            ],
        )
        numeric_columns = ["open", "high", "low", "close", "volume"]
        frame[numeric_columns] = frame[numeric_columns].astype(float)
        frame["time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        return frame[["time", "open", "high", "low", "close", "volume"]]

    def _fetch_mt5_rates(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        if mt5 is None:
            return pd.DataFrame()

        if not mt5.initialize(path=settings.mt5_path):
            logger.warning("MT5 initialize failed: %s", mt5.last_error())
            return pd.DataFrame()

        if settings.mt5_login and settings.mt5_password and settings.mt5_server:
            authorized = mt5.login(
                login=int(settings.mt5_login),
                password=settings.mt5_password,
                server=settings.mt5_server,
            )
            if not authorized:
                logger.warning("MT5 login failed: %s", mt5.last_error())
                return pd.DataFrame()

        rates = mt5.copy_rates_from_pos(symbol, self.MT5_TIMEFRAME_MAP.get(timeframe), 0, limit)
        if rates is None or len(rates) == 0:
            logger.warning("No MT5 rates returned for %s", symbol)
            return pd.DataFrame()

        frame = pd.DataFrame(rates)
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame.rename(columns={"tick_volume": "volume"}, inplace=True)
        return frame[["time", "open", "high", "low", "close", "volume"]]

    def _generate_synthetic_ohlcv(self, symbol: str, limit: int) -> pd.DataFrame:
        seed = abs(hash(symbol)) % 10_000
        rng = np.random.default_rng(seed)
        base_price = 1.1 if symbol.endswith("USD") and len(symbol) <= 6 else 50_000.0
        start = datetime.now(UTC) - timedelta(minutes=15 * limit)

        closes = [base_price]
        for _ in range(limit - 1):
            closes.append(closes[-1] * (1 + rng.normal(0, 0.0025)))
        closes = np.array(closes)

        highs = closes * (1 + rng.uniform(0.0005, 0.003, size=limit))
        lows = closes * (1 - rng.uniform(0.0005, 0.003, size=limit))
        opens = np.concatenate([[closes[0]], closes[:-1]])
        volumes = rng.integers(100, 1000, size=limit)

        times = [start + timedelta(minutes=15 * idx) for idx in range(limit)]
        return pd.DataFrame(
            {
                "time": times,
                "open": opens,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            }
        )
