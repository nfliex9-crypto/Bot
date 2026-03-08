"""
Trade Manager.

Manages open trades:
- Monitors price against TP1/TP2/TP3 levels
- Executes partial closes at TP1 and TP2
- Moves stop to break-even after TP1 is hit
- Checks stop loss hit
"""
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("trade_manager")


@dataclass
class TradeUpdate:
    trade_id: int
    action: str              # "none" | "close_partial" | "close_full" | "move_be" | "update_sl"
    new_sl: Optional[float] = None
    close_pct: float = 0.0   # 0-1, % of position to close
    close_price: Optional[float] = None
    tp_level: Optional[int] = None  # 1, 2, or 3
    pnl: float = 0.0
    reason: str = ""


class TradeManager:
    """
    Monitors and manages open trade positions.

    Trade lifecycle:
    1. Trade opens at entry_price
    2. Monitor for TP1 hit → close 33% + move SL to BE
    3. Monitor for TP2 hit → close 33%
    4. Monitor for TP3 hit → close remaining 34%
    5. Monitor for SL hit → full close

    Break-even logic:
    - After TP1 is hit, SL moves to entry price + small buffer
    """

    def __init__(
        self,
        tp1_ratio: float = None,
        tp2_ratio: float = None,
        tp3_ratio: float = None,
        breakeven_after_tp1: bool = None,
        be_buffer_pips: float = 2.0,
    ):
        self.tp1_ratio = tp1_ratio or settings.TP1_RATIO
        self.tp2_ratio = tp2_ratio or settings.TP2_RATIO
        self.tp3_ratio = tp3_ratio or settings.TP3_RATIO
        self.breakeven_after_tp1 = breakeven_after_tp1 if breakeven_after_tp1 is not None \
            else settings.BREAKEVEN_AFTER_TP1
        self.be_buffer_pips = be_buffer_pips

    def check_trade(
        self,
        trade_id: int,
        direction: str,
        entry_price: float,
        current_price: float,
        stop_loss: float,
        take_profit_1: float,
        take_profit_2: Optional[float],
        take_profit_3: Optional[float],
        tp1_hit: bool,
        tp2_hit: bool,
        tp3_hit: bool,
        breakeven_moved: bool,
        lot_size: float,
        pip_value: float = 10.0,
    ) -> TradeUpdate:
        """
        Check current price against trade levels and return required action.
        """
        # --- Stop Loss Hit ---
        if direction == "long" and current_price <= stop_loss:
            pnl = (current_price - entry_price) * lot_size * 100000 / pip_value \
                if pip_value > 0 else (current_price - entry_price)
            return TradeUpdate(
                trade_id=trade_id,
                action="close_full",
                close_pct=1.0,
                close_price=current_price,
                pnl=pnl,
                reason="stop_loss_hit",
            )

        if direction == "short" and current_price >= stop_loss:
            pnl = (entry_price - current_price) * lot_size * 100000 / pip_value \
                if pip_value > 0 else (entry_price - current_price)
            return TradeUpdate(
                trade_id=trade_id,
                action="close_full",
                close_pct=1.0,
                close_price=current_price,
                pnl=pnl,
                reason="stop_loss_hit",
            )

        # --- TP3 (Full close remaining) ---
        if take_profit_3 is not None and not tp3_hit:
            if (direction == "long" and current_price >= take_profit_3) or \
               (direction == "short" and current_price <= take_profit_3):
                return TradeUpdate(
                    trade_id=trade_id,
                    action="close_full",
                    close_pct=1.0,
                    close_price=current_price,
                    tp_level=3,
                    reason="tp3_hit",
                )

        # --- TP2 (Partial close) ---
        if take_profit_2 is not None and not tp2_hit:
            if (direction == "long" and current_price >= take_profit_2) or \
               (direction == "short" and current_price <= take_profit_2):
                return TradeUpdate(
                    trade_id=trade_id,
                    action="close_partial",
                    close_pct=0.33,
                    close_price=current_price,
                    tp_level=2,
                    reason="tp2_hit",
                )

        # --- TP1 (Partial close + move BE) ---
        if not tp1_hit:
            if (direction == "long" and current_price >= take_profit_1) or \
               (direction == "short" and current_price <= take_profit_1):

                action = "close_partial"
                new_sl = None

                if self.breakeven_after_tp1 and not breakeven_moved:
                    new_sl = self._calculate_breakeven(
                        direction, entry_price, stop_loss
                    )

                return TradeUpdate(
                    trade_id=trade_id,
                    action=action,
                    close_pct=0.33,
                    close_price=current_price,
                    new_sl=new_sl,
                    tp_level=1,
                    reason="tp1_hit",
                )

        # --- Break-even (if TP1 hit but BE not yet moved) ---
        if tp1_hit and self.breakeven_after_tp1 and not breakeven_moved:
            new_sl = self._calculate_breakeven(direction, entry_price, stop_loss)
            return TradeUpdate(
                trade_id=trade_id,
                action="move_be",
                new_sl=new_sl,
                reason="breakeven_move",
            )

        return TradeUpdate(trade_id=trade_id, action="none")

    def _calculate_breakeven(
        self,
        direction: str,
        entry_price: float,
        current_sl: float,
    ) -> float:
        """
        Calculate break-even stop loss (entry + small buffer).
        Buffer is a fraction of the entry-to-sl distance.
        """
        sl_distance = abs(entry_price - current_sl)
        buffer = sl_distance * 0.05  # 5% buffer

        if direction == "long":
            return entry_price + buffer
        else:
            return entry_price - buffer

    def calculate_unrealized_pnl(
        self,
        direction: str,
        entry_price: float,
        current_price: float,
        lot_size: float,
        market_type: str = "forex",
        symbol: str = "EURUSD",
    ) -> float:
        """Calculate unrealized P&L in account currency."""
        if direction == "long":
            price_diff = current_price - entry_price
        else:
            price_diff = entry_price - current_price

        if market_type == "crypto":
            return price_diff * lot_size
        else:
            # Forex: lot_size × 100,000 × price_diff (for USD quote pairs)
            pip_size = 0.01 if symbol.endswith("JPY") else 0.0001
            pips = price_diff / pip_size
            pip_value = 10.0  # USD per pip per standard lot (approximate)
            return pips * pip_value * lot_size

    def build_trade_summary(self, trades: list) -> dict:
        """Build a summary of all open trades."""
        if not trades:
            return {
                "open_count": 0,
                "total_unrealized_pnl": 0.0,
                "symbols": [],
            }

        return {
            "open_count": len(trades),
            "total_unrealized_pnl": sum(t.get("pnl", 0) for t in trades),
            "symbols": [t.get("symbol") for t in trades],
        }
