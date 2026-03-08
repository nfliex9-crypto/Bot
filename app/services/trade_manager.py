from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Trade
from app.risk.manager import RiskManager


class TradeManager:
    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager

    def manage_open_trades(self, db: Session, latest_prices: dict[str, float]) -> list[str]:
        notes: list[str] = []
        open_trades = db.query(Trade).filter(Trade.status == "open").all()
        for trade in open_trades:
            current = latest_prices.get(trade.symbol)
            if current is None:
                continue
            notes.extend(self._update_trade_state(db, trade, current))
        db.commit()
        return notes

    def _update_trade_state(self, db: Session, trade: Trade, current_price: float) -> list[str]:
        notes: list[str] = []
        side = trade.side
        risk_distance = abs(trade.entry_price - trade.stop_loss)
        if risk_distance <= 0:
            return notes

        risk_amount = trade.risk_amount
        partial = risk_amount / 3.0
        realized = float(trade.metadata_json.get("realized_pnl", 0.0)) if trade.metadata_json else 0.0

        tp1_hit = (current_price >= trade.tp1) if side == "buy" else (current_price <= trade.tp1)
        tp2_hit = (current_price >= trade.tp2) if side == "buy" else (current_price <= trade.tp2)
        tp3_hit = (current_price >= trade.tp3) if side == "buy" else (current_price <= trade.tp3)
        sl_hit = (current_price <= trade.stop_loss) if side == "buy" else (current_price >= trade.stop_loss)

        if tp1_hit and not trade.tp1_hit:
            trade.tp1_hit = True
            realized += partial * 1.0
            trade.stop_loss = trade.entry_price  # Break-even after TP1
            notes.append(f"{trade.symbol}: TP1 hit -> stop moved to break-even")

        if tp2_hit and not trade.tp2_hit:
            trade.tp2_hit = True
            realized += partial * 1.5
            notes.append(f"{trade.symbol}: TP2 hit")

        if tp3_hit and not trade.tp3_hit:
            trade.tp3_hit = True
            realized += partial * 2.0
            trade.status = "closed"
            trade.closed_at = datetime.now(timezone.utc)
            notes.append(f"{trade.symbol}: TP3 hit -> trade closed")

        if sl_hit and trade.status == "open":
            if trade.tp1_hit:
                notes.append(f"{trade.symbol}: stopped at break-even/managed SL")
            else:
                realized -= risk_amount
                notes.append(f"{trade.symbol}: full stop-loss hit")
            trade.status = "closed"
            trade.closed_at = datetime.now(timezone.utc)

        trade.metadata_json = {**(trade.metadata_json or {}), "realized_pnl": realized, "last_price": current_price}

        if trade.status == "closed":
            self.risk_manager.apply_realized_pnl(realized)
            notes.append(f"{trade.symbol}: realized PnL {realized:.2f}")
            db.add(trade)

        return notes

