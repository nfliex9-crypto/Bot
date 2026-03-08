from datetime import datetime, timezone

import numpy as np
import pandas as pd
from binance import AsyncClient

try:
    import MetaTrader5 as mt5  # type: ignore
except Exception:  # pragma: no cover
    mt5 = None


TIMEFRAME_MAP_MT5 = {
    "M5": getattr(mt5, "TIMEFRAME_M5", None),
    "M15": getattr(mt5, "TIMEFRAME_M15", None),
    "H1": getattr(mt5, "TIMEFRAME_H1", None),
}

TIMEFRAME_MAP_BINANCE = {"M5": "5m", "M15": "15m", "H1": "1h"}


def _synthetic_ohlcv(rows: int = 300) -> pd.DataFrame:
    base = 100 + np.cumsum(np.random.normal(0, 0.2, size=rows))
    high = base + np.random.uniform(0.05, 0.5, size=rows)
    low = base - np.random.uniform(0.05, 0.5, size=rows)
    open_ = np.roll(base, 1)
    open_[0] = base[0]
    volume = np.random.uniform(100, 5000, size=rows)
    idx = pd.date_range(end=datetime.now(tz=timezone.utc), periods=rows, freq="5min")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": base, "volume": volume},
        index=idx,
    )


class MarketDataGateway:
    def __init__(self, binance_key: str | None, binance_secret: str | None, binance_testnet: bool = True) -> None:
        self.binance_key = binance_key
        self.binance_secret = binance_secret
        self.binance_testnet = binance_testnet
        self._binance_client: AsyncClient | None = None

    async def _get_binance_client(self) -> AsyncClient:
        if self._binance_client is None:
            self._binance_client = await AsyncClient.create(
                api_key=self.binance_key,
                api_secret=self.binance_secret,
                testnet=self.binance_testnet,
            )
        return self._binance_client

    async def get_ohlcv(self, symbol: str, market: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        if market == "crypto":
            return await self._get_crypto_ohlcv(symbol, timeframe, bars)
        if market == "forex":
            return self._get_forex_ohlcv(symbol, timeframe, bars)
        raise ValueError(f"Unsupported market: {market}")

    async def _get_crypto_ohlcv(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        try:
            interval = TIMEFRAME_MAP_BINANCE[timeframe]
            client = await self._get_binance_client()
            raw = await client.get_klines(symbol=symbol, interval=interval, limit=bars)
            frame = pd.DataFrame(
                raw,
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
                    "taker_buy_base",
                    "taker_buy_quote",
                    "ignore",
                ],
            )
            frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
            frame = frame.set_index("open_time")
            for c in ("open", "high", "low", "close", "volume"):
                frame[c] = frame[c].astype(float)
            return frame[["open", "high", "low", "close", "volume"]]
        except Exception:
            return _synthetic_ohlcv(rows=bars)

    def _get_forex_ohlcv(self, symbol: str, timeframe: str, bars: int) -> pd.DataFrame:
        if mt5 is None:
            return _synthetic_ohlcv(rows=bars)
        mt5_tf = TIMEFRAME_MAP_MT5.get(timeframe)
        if mt5_tf is None:
            return _synthetic_ohlcv(rows=bars)

        if not mt5.initialize():
            return _synthetic_ohlcv(rows=bars)
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars)
        if rates is None or len(rates) == 0:
            return _synthetic_ohlcv(rows=bars)
        frame = pd.DataFrame(rates)
        frame["time"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame = frame.set_index("time")
        return frame[["open", "high", "low", "close", "tick_volume"]].rename(columns={"tick_volume": "volume"})
