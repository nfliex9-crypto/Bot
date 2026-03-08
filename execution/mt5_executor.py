from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config.settings import settings
from core.models import Direction, Market, OpenTrade, TradeSignal, TradeStatus
from execution.base_executor import BaseExecutor
from utils.helpers import generate_trade_id
from utils.logger import get_logger

logger = get_logger(__name__)

# MetaTrader5 is only available on Windows; we import lazily and mock otherwise
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not available — MT5 executor running in mock mode")


_TF_MAP = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 16385,
    "1h": 16388,
    "4h": 16390,
    "1d": 16408,
}


class PaperMT5Store:
    """In-memory paper trade store for MT5."""

    def __init__(self) -> None:
        self._trades: Dict[str, OpenTrade] = {}
        self._balance: float = settings.account_balance
        self._equity: float = settings.account_balance

    def add_trade(self, trade: OpenTrade) -> None:
        self._trades[trade.trade_id] = trade

    def update_equity(self, current_prices: Dict[str, float]) -> None:
        pnl = 0.0
        for t in self._trades.values():
            if t.status == TradeStatus.OPEN and t.symbol in current_prices:
                cp = current_prices[t.symbol]
                if t.direction == Direction.LONG:
                    pnl += (cp - t.entry_price) * t.lot_size * 100_000
                else:
                    pnl += (t.entry_price - cp) * t.lot_size * 100_000
        self._equity = self._balance + pnl

    def get_open_trades(self) -> List[OpenTrade]:
        return [t for t in self._trades.values() if t.status == TradeStatus.OPEN]

    @property
    def balance(self) -> float:
        return self._balance

    @property
    def equity(self) -> float:
        return self._equity


class MT5Executor(BaseExecutor):
    """
    MetaTrader 5 executor.

    In paper mode: executes against an internal in-memory store with
    realistic fill simulation.
    In live mode: routes orders through the MT5 terminal API.
    """

    def __init__(self) -> None:
        super().__init__(market=Market.FOREX, paper_mode=settings.is_paper)
        self._paper_store = PaperMT5Store()

    # ------------------------------------------------------------------
    async def connect(self) -> bool:
        if self._paper_mode or not MT5_AVAILABLE:
            logger.info("MT5 Executor: connected in PAPER mode")
            self._connected = True
            return True

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._mt5_connect)
        if result:
            self._connected = True
            logger.info("MT5 Executor: connected to %s", settings.mt5_server)
        return result

    def _mt5_connect(self) -> bool:
        kwargs = dict(login=settings.mt5_login, password=settings.mt5_password, server=settings.mt5_server)
        if settings.mt5_path:
            kwargs["path"] = settings.mt5_path
        return bool(mt5.initialize(**kwargs))

    async def disconnect(self) -> None:
        if not self._paper_mode and MT5_AVAILABLE and self._connected:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, mt5.shutdown)
        self._connected = False
        logger.info("MT5 Executor: disconnected")

    # ------------------------------------------------------------------
    async def get_account_balance(self) -> float:
        if self._paper_mode or not MT5_AVAILABLE:
            return self._paper_store.balance
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, mt5.account_info)
        return float(info.balance) if info else settings.account_balance

    async def get_account_equity(self) -> float:
        if self._paper_mode or not MT5_AVAILABLE:
            return self._paper_store.equity
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, mt5.account_info)
        return float(info.equity) if info else settings.account_balance

    # ------------------------------------------------------------------
    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 500,
    ) -> pd.DataFrame:
        if not MT5_AVAILABLE or self._paper_mode:
            return self._generate_mock_ohlcv(symbol, timeframe, limit)

        tf_const = _get_mt5_timeframe(timeframe)
        loop = asyncio.get_event_loop()
        rates = await loop.run_in_executor(
            None,
            lambda: mt5.copy_rates_from_pos(symbol, tf_const, 0, limit),
        )

        if rates is None or len(rates) == 0:
            logger.warning("MT5: no data returned for %s %s", symbol, timeframe)
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        df = df.rename(
            columns={
                "time": "timestamp",
                "tick_volume": "volume",
                "real_volume": "real_volume",
            }
        )
        df = df.set_index("timestamp")
        df = df[["open", "high", "low", "close", "volume"]].copy()
        return df.sort_index()

    async def get_current_price(self, symbol: str) -> Tuple[float, float]:
        if not MT5_AVAILABLE or self._paper_mode:
            return (1.10000, 1.10010)
        loop = asyncio.get_event_loop()
        tick = await loop.run_in_executor(None, lambda: mt5.symbol_info_tick(symbol))
        if tick:
            return (float(tick.bid), float(tick.ask))
        return (0.0, 0.0)

    # ------------------------------------------------------------------
    async def place_order(self, signal: TradeSignal) -> Optional[str]:
        self.log_order(
            "PLACE",
            signal.symbol,
            {
                "direction": signal.direction.value,
                "entry": signal.entry_price,
                "sl": signal.stop_loss,
                "tp1": signal.tp1,
                "lot": signal.lot_size,
                "confidence": signal.ai_confidence,
            },
        )

        if self._paper_mode or not MT5_AVAILABLE:
            return self._paper_place_order(signal)

        loop = asyncio.get_event_loop()
        order_id = await loop.run_in_executor(None, lambda: self._mt5_place_order(signal))
        return order_id

    def _paper_place_order(self, signal: TradeSignal) -> str:
        trade = OpenTrade(
            trade_id=signal.trade_id,
            symbol=signal.symbol,
            market=signal.market,
            direction=signal.direction,
            entry_price=signal.entry_price,
            current_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            lot_size=signal.lot_size,
            risk_amount=signal.risk_amount,
            opened_at=datetime.now(timezone.utc),
            broker_order_id=f"PAPER_{signal.trade_id}",
        )
        self._paper_store.add_trade(trade)
        return trade.broker_order_id  # type: ignore[return-value]

    def _mt5_place_order(self, signal: TradeSignal) -> Optional[str]:
        order_type = mt5.ORDER_TYPE_BUY if signal.direction == Direction.LONG else mt5.ORDER_TYPE_SELL
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": signal.symbol,
            "volume": signal.lot_size,
            "type": order_type,
            "price": signal.entry_price,
            "sl": signal.stop_loss,
            "tp": signal.tp1,
            "deviation": 20,
            "magic": 20240101,
            "comment": f"AI_BOT_{signal.trade_id}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            return str(result.order)
        logger.error("MT5 order failed: %s", result)
        return None

    # ------------------------------------------------------------------
    async def modify_stop_loss(self, trade: OpenTrade, new_sl: float) -> bool:
        self.log_order("MODIFY_SL", trade.symbol, {"order": trade.broker_order_id, "new_sl": new_sl})
        if self._paper_mode or not MT5_AVAILABLE:
            if trade.trade_id in self._paper_store._trades:
                self._paper_store._trades[trade.trade_id].stop_loss = new_sl
            return True
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._mt5_modify_sl(trade, new_sl)
        )

    def _mt5_modify_sl(self, trade: OpenTrade, new_sl: float) -> bool:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": int(trade.broker_order_id or 0),
            "sl": new_sl,
        }
        result = mt5.order_send(request)
        return bool(result and result.retcode == mt5.TRADE_RETCODE_DONE)

    # ------------------------------------------------------------------
    async def close_partial(self, trade: OpenTrade, close_pct: float) -> bool:
        close_volume = round(trade.lot_size * close_pct, 2)
        self.log_order(
            "PARTIAL_CLOSE",
            trade.symbol,
            {"volume": close_volume, "pct": close_pct},
        )
        if self._paper_mode or not MT5_AVAILABLE:
            return True   # Simplified paper simulation
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._mt5_close_partial(trade, close_volume)
        )

    def _mt5_close_partial(self, trade: OpenTrade, volume: float) -> bool:
        close_type = mt5.ORDER_TYPE_SELL if trade.direction == Direction.LONG else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(trade.symbol)
        close_price = tick.bid if trade.direction == Direction.LONG else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": int(trade.broker_order_id or 0),
            "symbol": trade.symbol,
            "volume": volume,
            "type": close_type,
            "price": close_price,
            "deviation": 20,
            "magic": 20240101,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return bool(result and result.retcode == mt5.TRADE_RETCODE_DONE)

    # ------------------------------------------------------------------
    async def close_trade(self, trade: OpenTrade) -> bool:
        self.log_order("CLOSE", trade.symbol, {"order": trade.broker_order_id})
        if self._paper_mode or not MT5_AVAILABLE:
            if trade.trade_id in self._paper_store._trades:
                self._paper_store._trades[trade.trade_id].status = TradeStatus.CLOSED
            return True
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._mt5_close_trade(trade))

    def _mt5_close_trade(self, trade: OpenTrade) -> bool:
        position_id = int(trade.broker_order_id or 0)
        close_type = mt5.ORDER_TYPE_SELL if trade.direction == Direction.LONG else mt5.ORDER_TYPE_BUY
        tick = mt5.symbol_info_tick(trade.symbol)
        close_price = tick.bid if trade.direction == Direction.LONG else tick.ask
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "position": position_id,
            "symbol": trade.symbol,
            "volume": trade.lot_size,
            "type": close_type,
            "price": close_price,
            "deviation": 20,
            "magic": 20240101,
            "comment": "AI_BOT_CLOSE",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return bool(result and result.retcode == mt5.TRADE_RETCODE_DONE)

    # ------------------------------------------------------------------
    async def get_open_trades(self) -> List[OpenTrade]:
        if self._paper_mode or not MT5_AVAILABLE:
            return self._paper_store.get_open_trades()
        loop = asyncio.get_event_loop()
        positions = await loop.run_in_executor(None, mt5.positions_get)
        if not positions:
            return []
        result = []
        for pos in positions:
            direction = Direction.LONG if pos.type == 0 else Direction.SHORT
            result.append(
                OpenTrade(
                    trade_id=str(pos.ticket),
                    symbol=pos.symbol,
                    market=Market.FOREX,
                    direction=direction,
                    entry_price=pos.price_open,
                    current_price=pos.price_current,
                    stop_loss=pos.sl,
                    tp1=pos.tp,
                    tp2=pos.tp,
                    tp3=pos.tp,
                    lot_size=pos.volume,
                    risk_amount=0.0,
                    opened_at=datetime.fromtimestamp(pos.time, tz=timezone.utc),
                    broker_order_id=str(pos.ticket),
                    unrealised_pnl=pos.profit,
                )
            )
        return result

    # ------------------------------------------------------------------
    @staticmethod
    def _generate_mock_ohlcv(symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Generate synthetic OHLCV data for testing."""
        import numpy as np
        np.random.seed(hash(symbol + timeframe) % 2**31)
        dates = pd.date_range(end=pd.Timestamp.utcnow(), periods=limit, freq="5min", tz="UTC")
        close = 1.10 + np.cumsum(np.random.randn(limit) * 0.0002)
        high = close + np.abs(np.random.randn(limit)) * 0.0005
        low = close - np.abs(np.random.randn(limit)) * 0.0005
        open_ = close + np.random.randn(limit) * 0.0002
        volume = np.random.randint(100, 1000, size=limit).astype(float)
        df = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=dates,
        )
        return df.sort_index()


def _get_mt5_timeframe(tf: str):
    if not MT5_AVAILABLE:
        return None
    tf_map = {
        "1m": mt5.TIMEFRAME_M1,
        "5m": mt5.TIMEFRAME_M5,
        "15m": mt5.TIMEFRAME_M15,
        "30m": mt5.TIMEFRAME_M30,
        "1h": mt5.TIMEFRAME_H1,
        "4h": mt5.TIMEFRAME_H4,
        "1d": mt5.TIMEFRAME_D1,
    }
    return tf_map.get(tf, mt5.TIMEFRAME_M5)
