from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.domain.models import AccountSnapshot, MarketType, OpenTrade, SizedTradeSignal, TradeSide
from app.execution.base import BrokerOrderResult

try:
    import MetaTrader5 as mt5
except ImportError:  # pragma: no cover - optional runtime dependency
    mt5 = None


class MT5Broker:
    def __init__(self, settings: Settings):
        self.settings = settings
        if mt5 is None:
            raise RuntimeError("MetaTrader5 package is not installed")
        initialized = mt5.initialize(
            path=settings.mt5_path,
            login=settings.mt5_login,
            password=settings.mt5_password,
            server=settings.mt5_server,
        )
        if not initialized:
            raise RuntimeError(f"MetaTrader5 initialize failed: {mt5.last_error()}")

    async def get_account_snapshot(self, market: MarketType) -> AccountSnapshot:
        info = await asyncio.to_thread(mt5.account_info)
        if info is None:
            raise RuntimeError(f"MT5 account_info failed: {mt5.last_error()}")
        return AccountSnapshot(
            balance=float(info.balance),
            equity=float(info.equity),
            peak_balance=max(float(info.balance), float(info.equity)),
            session_trade_count=0,
        )

    async def place_trade(self, signal: SizedTradeSignal) -> BrokerOrderResult:
        await asyncio.to_thread(mt5.symbol_select, signal.symbol, True)
        tick = await asyncio.to_thread(mt5.symbol_info_tick, signal.symbol)
        if tick is None:
            raise RuntimeError(f"MT5 tick unavailable for {signal.symbol}")

        order_type = mt5.ORDER_TYPE_BUY if signal.side == TradeSide.BUY else mt5.ORDER_TYPE_SELL
        price = float(tick.ask if signal.side == TradeSide.BUY else tick.bid)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": signal.symbol,
            "volume": signal.position_size,
            "type": order_type,
            "price": price,
            "sl": signal.stop_loss,
            "deviation": 20,
            "magic": 20260308,
            "comment": "ai-trading-bot",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = await asyncio.to_thread(mt5.order_send, request)
        if result is None:
            raise RuntimeError(f"MT5 order_send failed: {mt5.last_error()}")
        return BrokerOrderResult(
            broker_trade_id=str(result.order or result.deal),
            fill_price=price,
            filled_size=signal.position_size,
            status=str(result.retcode),
        )

    async def move_stop_to_break_even(self, trade: OpenTrade) -> None:
        if not trade.broker_trade_id:
            return
        positions = await asyncio.to_thread(mt5.positions_get, ticket=int(trade.broker_trade_id))
        if not positions:
            return
        position = positions[0]
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": position.ticket,
            "symbol": trade.symbol,
            "sl": trade.entry_price,
            "tp": 0.0,
        }
        await asyncio.to_thread(mt5.order_send, request)

    async def close_partial(self, trade: OpenTrade, quantity: float, reason: str) -> None:
        await asyncio.to_thread(mt5.symbol_select, trade.symbol, True)
        tick = await asyncio.to_thread(mt5.symbol_info_tick, trade.symbol)
        side = mt5.ORDER_TYPE_SELL if trade.side == TradeSide.BUY else mt5.ORDER_TYPE_BUY
        price = float(tick.bid if trade.side == TradeSide.BUY else tick.ask)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": trade.symbol,
            "volume": quantity,
            "type": side,
            "position": int(trade.broker_trade_id) if trade.broker_trade_id else 0,
            "price": price,
            "deviation": 20,
            "magic": 20260308,
            "comment": reason,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        await asyncio.to_thread(mt5.order_send, request)

    async def close_trade(self, trade: OpenTrade, reason: str) -> None:
        await self.close_partial(trade, trade.remaining_size, reason)

    async def book_realized_pnl(self, market: MarketType, pnl: float) -> None:
        return None
