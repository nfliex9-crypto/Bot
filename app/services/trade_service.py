from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.execution.base import BaseExecutor, OrderRequest
from app.models import Trade
from app.schemas import Signal


@dataclass
class MarketTick:
    symbol: str
    price: float


class TradeService:
    def __init__(self, executor_forex: BaseExecutor, executor_crypto: BaseExecutor, mode: str):
        self.executor_forex = executor_forex
        self.executor_crypto = executor_crypto
        self.mode = mode

    def _executor_for(self, market: str) -> BaseExecutor:
        return self.executor_forex if market == "forex" else self.executor_crypto

    def open_trade(self, session: Session, signal: Signal, quantity: float, confidence: float) -> Trade | None:
        executor = self._executor_for(signal.market)
        result = executor.place_order(
            request=OrderRequest(
                market=signal.market,
                symbol=signal.symbol,
                side=signal.side,
                quantity=quantity,
                price=signal.entry_price,
                stop_loss=signal.stop_loss,
            )
        )
        if not result.success:
            return None

        trade = Trade(
            market=signal.market,
            symbol=signal.symbol,
            side=signal.side,
            mode=self.mode,
            quantity=quantity,
            entry_price=result.filled_price,
            stop_loss=signal.stop_loss,
            tp1=signal.tp1,
            tp2=signal.tp2,
            tp3=signal.tp3,
            status="open",
            remaining_qty=quantity,
            realized_pnl=0.0,
            confidence=confidence,
            strategy_notes=signal.notes,
            execution_ref=result.execution_ref,
        )
        session.add(trade)
        session.flush()
        return trade

    def update_open_trades(self, session: Session, tick: MarketTick) -> None:
        trades = session.execute(
            select(Trade).where(Trade.symbol == tick.symbol, Trade.status == "open").order_by(Trade.created_at.asc())
        ).scalars()

        for trade in trades:
            is_buy = trade.side == "buy"
            reached_sl = tick.price <= trade.stop_loss if is_buy else tick.price >= trade.stop_loss
            if reached_sl:
                self._close_trade(session, trade, tick.price, status="stopped")
                continue

            if (not trade.hit_tp1) and (tick.price >= trade.tp1 if is_buy else tick.price <= trade.tp1):
                self._take_partial(session, trade, level="tp1", price=tick.price, fraction=0.5)
                if not trade.moved_to_breakeven:
                    trade.stop_loss = trade.entry_price
                    trade.moved_to_breakeven = True

            if (not trade.hit_tp2) and (tick.price >= trade.tp2 if is_buy else tick.price <= trade.tp2):
                self._take_partial(session, trade, level="tp2", price=tick.price, fraction=0.3)

            if (not trade.hit_tp3) and (tick.price >= trade.tp3 if is_buy else tick.price <= trade.tp3):
                self._take_partial(session, trade, level="tp3", price=tick.price, fraction=1.0)
                self._close_trade(session, trade, tick.price, status="closed")

    def _take_partial(self, session: Session, trade: Trade, level: str, price: float, fraction: float) -> None:
        qty = round(trade.remaining_qty * fraction, 8)
        if qty <= 0:
            return
        executor = self._executor_for(trade.market)
        result = executor.close_partial(symbol=trade.symbol, side=trade.side, quantity=qty)
        if not result.success:
            return

        direction = 1 if trade.side == "buy" else -1
        trade.realized_pnl += (price - trade.entry_price) * qty * direction
        trade.remaining_qty = max(0.0, trade.remaining_qty - qty)
        if level == "tp1":
            trade.hit_tp1 = True
        elif level == "tp2":
            trade.hit_tp2 = True
        elif level == "tp3":
            trade.hit_tp3 = True
        session.add(trade)

    def _close_trade(self, session: Session, trade: Trade, price: float, status: str) -> None:
        if trade.remaining_qty > 0:
            direction = 1 if trade.side == "buy" else -1
            trade.realized_pnl += (price - trade.entry_price) * trade.remaining_qty * direction
            trade.remaining_qty = 0.0
        trade.status = status
        session.add(trade)

