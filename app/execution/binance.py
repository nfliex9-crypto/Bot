from __future__ import annotations

import asyncio
from typing import Any

import ccxt

from app.core.config import Settings
from app.domain.models import AccountSnapshot, MarketType, OpenTrade, SizedTradeSignal, TradeSide
from app.execution.base import BrokerOrderResult


class BinanceBroker:
    def __init__(self, settings: Settings):
        self.exchange = ccxt.binance(
            {
                "apiKey": settings.binance_api_key,
                "secret": settings.binance_api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "future"},
            }
        )
        if settings.binance_testnet:
            self.exchange.set_sandbox_mode(True)

    async def get_account_snapshot(self, market: MarketType) -> AccountSnapshot:
        balance = await asyncio.to_thread(self.exchange.fetch_balance)
        total_usdt = float(balance.get("total", {}).get("USDT", 0.0))
        if total_usdt <= 0:
            total_usdt = float(balance.get("free", {}).get("USDT", 0.0))
        return AccountSnapshot(
            balance=total_usdt,
            equity=total_usdt,
            peak_balance=total_usdt,
            session_trade_count=0,
        )

    async def place_trade(self, signal: SizedTradeSignal) -> BrokerOrderResult:
        side = "buy" if signal.side == TradeSide.BUY else "sell"
        order = await asyncio.to_thread(
            self.exchange.create_order,
            signal.symbol,
            "market",
            side,
            signal.position_size,
        )
        filled = float(order.get("filled") or signal.position_size)
        average = float(order.get("average") or signal.entry)
        return BrokerOrderResult(
            broker_trade_id=str(order.get("id")),
            fill_price=average,
            filled_size=filled,
            status=str(order.get("status", "open")),
        )

    async def move_stop_to_break_even(self, trade: OpenTrade) -> None:
        return None

    async def close_partial(self, trade: OpenTrade, quantity: float, reason: str) -> None:
        side = "sell" if trade.side == TradeSide.BUY else "buy"
        params: dict[str, Any] = {"reduceOnly": True}
        await asyncio.to_thread(self.exchange.create_order, trade.symbol, "market", side, quantity, None, params)

    async def close_trade(self, trade: OpenTrade, reason: str) -> None:
        await self.close_partial(trade, trade.remaining_size, reason)

    async def book_realized_pnl(self, market: MarketType, pnl: float) -> None:
        return None
