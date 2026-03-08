from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from app.config import Settings

logger = logging.getLogger(__name__)

_TF_MAP = {
    "M1": 1,
    "M5": 5,
    "M15": 15,
    "M30": 30,
    "H1": 60,
}


class MT5MarketDataClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._mt5 = None
        self._connected = False
        self._try_import()

    def _try_import(self) -> None:
        try:
            import MetaTrader5 as mt5  # type: ignore

            self._mt5 = mt5
        except Exception as exc:  # pragma: no cover - optional dependency runtime
            logger.warning("MetaTrader5 package unavailable: %s", exc)
            self._mt5 = None

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> bool:
        if self._mt5 is None:
            return False
        if self._connected:
            return True
        ok = self._mt5.initialize(path=self.settings.mt5_path) if self.settings.mt5_path else self._mt5.initialize()
        if not ok:
            logger.error("MT5 initialize failed")
            return False
        if self.settings.mt5_login and self.settings.mt5_password and self.settings.mt5_server:
            login_ok = self._mt5.login(
                login=int(self.settings.mt5_login),
                password=self.settings.mt5_password,
                server=self.settings.mt5_server,
            )
            if not login_ok:
                logger.error("MT5 login failed")
                return False
        self._connected = True
        return True

    def get_ohlcv(self, symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        if self._mt5 is None or not self.connect():
            return self._synthetic_ohlcv(timeframe, bars)

        mt5_tf = getattr(self._mt5, f"TIMEFRAME_{timeframe}", None)
        if mt5_tf is None:
            return self._synthetic_ohlcv(timeframe, bars)

        rates = self._mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars)
        if rates is None or len(rates) == 0:
            return self._synthetic_ohlcv(timeframe, bars)

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df.rename(columns={"tick_volume": "volume"})[["time", "open", "high", "low", "close", "volume"]]

    def _synthetic_ohlcv(self, timeframe: str, bars: int) -> pd.DataFrame:
        step_minutes = _TF_MAP.get(timeframe, 5)
        now = datetime.now(timezone.utc)
        idx = pd.date_range(end=now, periods=bars, freq=f"{step_minutes}min")
        base = pd.Series(range(bars), dtype=float) * 0.02 + 100
        close = base + (pd.Series(((-1) ** (i % 7)) * 0.03 for i in range(bars)).cumsum() * 0.1)
        open_ = close.shift(1).fillna(close.iloc[0])
        high = pd.concat([open_, close], axis=1).max(axis=1) + 0.05
        low = pd.concat([open_, close], axis=1).min(axis=1) - 0.05
        volume = pd.Series(1000, index=range(bars), dtype=float)
        return pd.DataFrame({"time": idx, "open": open_, "high": high, "low": low, "close": close, "volume": volume})

    def info(self) -> dict[str, Any]:
        return {"connected": self._connected}

