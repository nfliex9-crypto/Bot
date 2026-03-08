from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .domain import InstrumentSpec, MarketType

try:
    from binance.client import Client as BinanceClient
except Exception:  # pragma: no cover - optional dependency may fail outside live environment
    BinanceClient = None

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - optional dependency may fail outside live environment
    mt5 = None


class DataFeed(ABC):
    market: MarketType

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def current_price(self, symbol: str) -> float:
        raise NotImplementedError

    @abstractmethod
    def instrument_spec(self, symbol: str) -> InstrumentSpec:
        raise NotImplementedError


class BinanceDataFeed(DataFeed):
    market = MarketType.CRYPTO
    INTERVALS = {
        "1h": "1h",
        "15m": "15m",
        "5m": "5m",
    }

    def __init__(self, api_key: str | None = None, api_secret: str | None = None, testnet: bool = True) -> None:
        if BinanceClient is None:
            raise RuntimeError("python-binance is not installed")
        self.client = BinanceClient(api_key=api_key, api_secret=api_secret, testnet=testnet)

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        interval = self.INTERVALS[timeframe]
        data = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        frame = pd.DataFrame(
            data,
            columns=[
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_asset_volume",
                "trades",
                "taker_buy_base",
                "taker_buy_quote",
                "ignore",
            ],
        )
        frame["timestamp"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
        numeric_cols = ["open", "high", "low", "close", "volume"]
        frame[numeric_cols] = frame[numeric_cols].astype(float)
        return frame.set_index("timestamp")[numeric_cols]

    def current_price(self, symbol: str) -> float:
        ticker = self.client.futures_mark_price(symbol=symbol)
        return float(ticker["markPrice"])

    def instrument_spec(self, symbol: str) -> InstrumentSpec:
        info = self.client.futures_exchange_info()
        symbol_info = next(item for item in info["symbols"] if item["symbol"] == symbol)
        lot_filter = next(f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
        price_filter = next(f for f in symbol_info["filters"] if f["filterType"] == "PRICE_FILTER")
        return InstrumentSpec(
            symbol=symbol,
            market=self.market,
            quantity_step=float(lot_filter["stepSize"]),
            min_quantity=float(lot_filter["minQty"]),
            tick_size=float(price_filter["tickSize"]),
            point_value=1.0,
        )


class MT5DataFeed(DataFeed):
    market = MarketType.FOREX
    TIMEFRAMES = {
        "1h": "TIMEFRAME_H1",
        "15m": "TIMEFRAME_M15",
        "5m": "TIMEFRAME_M5",
    }

    def __init__(self, *, login: int | None, password: str | None, server: str | None, path: str | None) -> None:
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        initialized = mt5.initialize(path=path, login=login, password=password, server=server)
        if not initialized:
            raise RuntimeError(f"Unable to initialize MetaTrader5: {mt5.last_error()}")

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        mt5_timeframe = getattr(mt5, self.TIMEFRAMES[timeframe])
        rates = mt5.copy_rates_from_pos(symbol, mt5_timeframe, 0, limit)
        if rates is None:
            raise RuntimeError(f"MT5 returned no data for {symbol}")
        frame = pd.DataFrame(rates)
        frame["timestamp"] = pd.to_datetime(frame["time"], unit="s", utc=True)
        frame = frame.rename(columns={"tick_volume": "volume"})
        return frame.set_index("timestamp")[["open", "high", "low", "close", "volume"]]

    def current_price(self, symbol: str) -> float:
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError(f"Unable to fetch tick for {symbol}")
        return float((tick.bid + tick.ask) / 2)

    def instrument_spec(self, symbol: str) -> InstrumentSpec:
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"Unable to fetch MT5 symbol info for {symbol}")
        contract_size = float(info.trade_contract_size or 100000.0)
        return InstrumentSpec(
            symbol=symbol,
            market=self.market,
            quantity_step=float(info.volume_step or 0.01),
            min_quantity=float(info.volume_min or 0.01),
            tick_size=float(info.point or 0.0001),
            contract_size=contract_size,
            point_value=contract_size,
        )


class FallbackDataFeed(DataFeed):
    def __init__(self, market: MarketType, store: dict[str, pd.DataFrame]) -> None:
        self.market = market
        self.store = store

    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
        key = f"{symbol}:{timeframe}"
        if key not in self.store:
            raise RuntimeError(f"No fallback data for {key}")
        return self.store[key].tail(limit).copy()

    def current_price(self, symbol: str) -> float:
        for key, frame in self.store.items():
            if key.startswith(f"{symbol}:"):
                return float(frame["close"].iloc[-1])
        raise RuntimeError(f"No fallback price for {symbol}")

    def instrument_spec(self, symbol: str) -> InstrumentSpec:
        return InstrumentSpec(symbol=symbol, market=self.market)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
