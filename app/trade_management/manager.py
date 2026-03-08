from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

from loguru import logger


class TradeAction(str, Enum):
    NONE = "none"
    PARTIAL_CLOSE_TP1 = "partial_close_tp1"
    PARTIAL_CLOSE_TP2 = "partial_close_tp2"
    CLOSE_TP3 = "close_tp3"
    MOVE_TO_BREAKEVEN = "move_to_breakeven"
    STOP_LOSS_HIT = "stop_loss_hit"


@dataclass
class ManagementDecision:
    action: TradeAction
    close_pct: float = 0.0  # portion of position to close
    new_stop_loss: float | None = None
    reason: str = ""


class TradeManager:
    """
    Active trade management:
      - TP1 (1R)  → close 33%, move SL to break-even
      - TP2 (1.5R) → close 33%
      - TP3 (2R)  → close remaining
    """

    def __init__(
        self,
        tp1_close_pct: float = 0.33,
        tp2_close_pct: float = 0.33,
    ) -> None:
        self._tp1_pct = tp1_close_pct
        self._tp2_pct = tp2_close_pct

    def evaluate(
        self,
        current_price: float,
        side: str,
        entry_price: float,
        stop_loss: float,
        tp1: float,
        tp2: float,
        tp3: float,
        tp1_hit: bool = False,
        tp2_hit: bool = False,
        tp3_hit: bool = False,
        break_even_set: bool = False,
    ) -> List[ManagementDecision]:
        """
        Evaluate current price against trade levels.
        Returns ordered list of management decisions to execute.
        """
        decisions: list[ManagementDecision] = []

        if side == "long":
            decisions = self._evaluate_long(
                current_price, entry_price, stop_loss,
                tp1, tp2, tp3, tp1_hit, tp2_hit, tp3_hit, break_even_set,
            )
        elif side == "short":
            decisions = self._evaluate_short(
                current_price, entry_price, stop_loss,
                tp1, tp2, tp3, tp1_hit, tp2_hit, tp3_hit, break_even_set,
            )

        return decisions

    def _evaluate_long(
        self,
        price: float,
        entry: float,
        sl: float,
        tp1: float,
        tp2: float,
        tp3: float,
        tp1_hit: bool,
        tp2_hit: bool,
        tp3_hit: bool,
        be_set: bool,
    ) -> list[ManagementDecision]:
        decisions: list[ManagementDecision] = []

        if price <= sl:
            decisions.append(
                ManagementDecision(
                    action=TradeAction.STOP_LOSS_HIT,
                    close_pct=1.0,
                    reason=f"Stop loss hit at {price:.5f}",
                )
            )
            return decisions

        if not tp3_hit and price >= tp3:
            decisions.append(
                ManagementDecision(
                    action=TradeAction.CLOSE_TP3,
                    close_pct=1.0,
                    reason=f"TP3 hit at {price:.5f} (2R)",
                )
            )
            return decisions

        if not tp1_hit and price >= tp1:
            decisions.append(
                ManagementDecision(
                    action=TradeAction.PARTIAL_CLOSE_TP1,
                    close_pct=self._tp1_pct,
                    reason=f"TP1 hit at {price:.5f} (1R)",
                )
            )
            if not be_set:
                decisions.append(
                    ManagementDecision(
                        action=TradeAction.MOVE_TO_BREAKEVEN,
                        new_stop_loss=entry,
                        reason="Moving SL to break-even after TP1",
                    )
                )

        if not tp2_hit and tp1_hit and price >= tp2:
            decisions.append(
                ManagementDecision(
                    action=TradeAction.PARTIAL_CLOSE_TP2,
                    close_pct=self._tp2_pct,
                    reason=f"TP2 hit at {price:.5f} (1.5R)",
                )
            )

        return decisions

    def _evaluate_short(
        self,
        price: float,
        entry: float,
        sl: float,
        tp1: float,
        tp2: float,
        tp3: float,
        tp1_hit: bool,
        tp2_hit: bool,
        tp3_hit: bool,
        be_set: bool,
    ) -> list[ManagementDecision]:
        decisions: list[ManagementDecision] = []

        if price >= sl:
            decisions.append(
                ManagementDecision(
                    action=TradeAction.STOP_LOSS_HIT,
                    close_pct=1.0,
                    reason=f"Stop loss hit at {price:.5f}",
                )
            )
            return decisions

        if not tp3_hit and price <= tp3:
            decisions.append(
                ManagementDecision(
                    action=TradeAction.CLOSE_TP3,
                    close_pct=1.0,
                    reason=f"TP3 hit at {price:.5f} (2R)",
                )
            )
            return decisions

        if not tp1_hit and price <= tp1:
            decisions.append(
                ManagementDecision(
                    action=TradeAction.PARTIAL_CLOSE_TP1,
                    close_pct=self._tp1_pct,
                    reason=f"TP1 hit at {price:.5f} (1R)",
                )
            )
            if not be_set:
                decisions.append(
                    ManagementDecision(
                        action=TradeAction.MOVE_TO_BREAKEVEN,
                        new_stop_loss=entry,
                        reason="Moving SL to break-even after TP1",
                    )
                )

        if not tp2_hit and tp1_hit and price <= tp2:
            decisions.append(
                ManagementDecision(
                    action=TradeAction.PARTIAL_CLOSE_TP2,
                    close_pct=self._tp2_pct,
                    reason=f"TP2 hit at {price:.5f} (1.5R)",
                )
            )

        return decisions
