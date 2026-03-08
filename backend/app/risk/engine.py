"""
Risk Engine

Enforces all risk management rules:
- 0.75% account risk per trade
- ATR-based stop loss positioning
- TP1 / TP2 / TP3 multi-target management
- Break-even trigger after TP1
- Max drawdown circuit breaker (15%)
- Session trade limit (3 per session)
- Lot size calculation for Forex and Crypto
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from datetime import datetime, timezone, date

logger = logging.getLogger(__name__)


# Forex pip values per standard lot (approximate USD values)
FOREX_PIP_VALUES = {
    "EURUSD": 10.0, "GBPUSD": 10.0, "AUDUSD": 10.0, "NZDUSD": 10.0,
    "USDCAD": 7.7, "USDCHF": 11.0, "USDJPY": 9.1,
    "GBPJPY": 9.1, "EURJPY": 9.1, "AUDJPY": 9.1,
    "XAUUSD": 1.0, "XAGUSD": 50.0,
}

# Crypto contract sizes (spot trading, 1 unit = 1 coin)
CRYPTO_CONTRACT_SIZE = 1.0


@dataclass
class RiskCalculation:
    symbol: str
    market: str
    direction: str
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float
    lot_size: float
    risk_amount: float
    risk_pct: float
    sl_pips: Optional[float]
    sl_distance: float
    rr_ratio_tp1: float
    rr_ratio_tp2: float
    rr_ratio_tp3: float
    approved: bool
    rejection_reason: Optional[str] = None


@dataclass
class BreakEvenResult:
    triggered: bool
    new_stop_loss: float
    reason: str


class RiskEngine:
    def __init__(
        self,
        risk_per_trade_pct: float = 0.75,
        max_drawdown_pct: float = 15.0,
        max_trades_per_session: int = 3,
        tp1_ratio: float = 1.5,
        tp2_ratio: float = 2.5,
        tp3_ratio: float = 4.0,
        break_even_buffer_pct: float = 0.1,
    ):
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_trades_per_session = max_trades_per_session
        self.tp1_ratio = tp1_ratio
        self.tp2_ratio = tp2_ratio
        self.tp3_ratio = tp3_ratio
        self.break_even_buffer_pct = break_even_buffer_pct

    def calculate_lot_size(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float,
        symbol: str,
        market: str,
    ) -> Tuple[float, float]:
        """
        Calculate position size based on risk percentage.

        Returns (lot_size, risk_amount_usd)
        """
        risk_amount = account_balance * (self.risk_per_trade_pct / 100.0)
        sl_distance = abs(entry_price - stop_loss)

        if sl_distance == 0:
            logger.warning(f"[{symbol}] SL distance is zero, cannot calculate lot size")
            return 0.0, 0.0

        if market == "FOREX":
            symbol_upper = symbol.upper().replace("/", "").replace("_", "")
            pip_value = FOREX_PIP_VALUES.get(symbol_upper, 10.0)

            # Determine pip size (most pairs 0.0001, JPY pairs 0.01)
            if "JPY" in symbol_upper:
                pip_size = 0.01
            elif symbol_upper in ("XAUUSD",):
                pip_size = 0.01
            else:
                pip_size = 0.0001

            sl_pips = sl_distance / pip_size
            # lot_size = risk_amount / (sl_pips * pip_value)
            lot_size = risk_amount / (sl_pips * pip_value)
            lot_size = round(max(0.01, min(lot_size, 100.0)), 2)

        elif market == "CRYPTO":
            # For crypto spot: risk_amount / sl_distance = quantity in base currency
            lot_size = risk_amount / sl_distance
            lot_size = round(max(0.001, lot_size), 6)
        else:
            lot_size = 0.01

        return lot_size, round(risk_amount, 2)

    def calculate_targets(
        self,
        entry_price: float,
        stop_loss: float,
        direction: str,
    ) -> Tuple[float, float, float]:
        """
        Calculate TP1, TP2, TP3 based on SL distance and risk:reward ratios.
        """
        sl_distance = abs(entry_price - stop_loss)

        if direction == "LONG":
            tp1 = entry_price + sl_distance * self.tp1_ratio
            tp2 = entry_price + sl_distance * self.tp2_ratio
            tp3 = entry_price + sl_distance * self.tp3_ratio
        else:
            tp1 = entry_price - sl_distance * self.tp1_ratio
            tp2 = entry_price - sl_distance * self.tp2_ratio
            tp3 = entry_price - sl_distance * self.tp3_ratio

        return tp1, tp2, tp3

    def check_break_even(
        self,
        entry_price: float,
        current_price: float,
        tp1: float,
        current_stop: float,
        direction: str,
        tp1_already_hit: bool = False,
    ) -> BreakEvenResult:
        """
        Determine if stop should be moved to break-even.
        Triggered when price reaches TP1.
        """
        if tp1_already_hit:
            return BreakEvenResult(
                triggered=False,
                new_stop_loss=current_stop,
                reason="Break-even already triggered"
            )

        buffer = abs(tp1 - entry_price) * self.break_even_buffer_pct

        if direction == "LONG":
            tp1_reached = current_price >= tp1
            if tp1_reached:
                new_sl = entry_price + buffer
                return BreakEvenResult(
                    triggered=True,
                    new_stop_loss=new_sl,
                    reason=f"Price reached TP1 ({tp1:.5f}), moving SL to break-even + buffer"
                )
        else:
            tp1_reached = current_price <= tp1
            if tp1_reached:
                new_sl = entry_price - buffer
                return BreakEvenResult(
                    triggered=True,
                    new_stop_loss=new_sl,
                    reason=f"Price reached TP1 ({tp1:.5f}), moving SL to break-even + buffer"
                )

        return BreakEvenResult(
            triggered=False,
            new_stop_loss=current_stop,
            reason="TP1 not yet reached"
        )

    def validate_trade(
        self,
        account_balance: float,
        account_equity: float,
        peak_equity: float,
        session_trades_today: int,
        session_date: str,
        entry_price: float,
        stop_loss: float,
        direction: str,
        symbol: str,
        market: str,
        confidence_score: float = 0.0,
        min_confidence: float = 0.65,
    ) -> RiskCalculation:
        """
        Full risk validation of a proposed trade.
        Returns RiskCalculation with approved=True/False.
        """
        # Check drawdown
        if peak_equity > 0:
            drawdown_pct = ((peak_equity - account_equity) / peak_equity) * 100
            if drawdown_pct >= self.max_drawdown_pct:
                return self._reject(
                    symbol, market, direction, entry_price, stop_loss,
                    f"Max drawdown {drawdown_pct:.1f}% exceeded limit {self.max_drawdown_pct}%"
                )

        # Check session trade limit
        today = date.today().isoformat()
        if session_date == today and session_trades_today >= self.max_trades_per_session:
            return self._reject(
                symbol, market, direction, entry_price, stop_loss,
                f"Session trade limit reached ({session_trades_today}/{self.max_trades_per_session})"
            )

        # Check confidence
        if confidence_score > 0 and confidence_score < min_confidence:
            return self._reject(
                symbol, market, direction, entry_price, stop_loss,
                f"AI confidence {confidence_score:.2f} below threshold {min_confidence}"
            )

        # Calculate lot size and risk
        lot_size, risk_amount = self.calculate_lot_size(
            account_balance, entry_price, stop_loss, symbol, market
        )

        if lot_size <= 0:
            return self._reject(
                symbol, market, direction, entry_price, stop_loss,
                "Could not calculate valid lot size"
            )

        # Calculate targets
        tp1, tp2, tp3 = self.calculate_targets(entry_price, stop_loss, direction)

        sl_distance = abs(entry_price - stop_loss)
        rr_tp1 = abs(tp1 - entry_price) / sl_distance if sl_distance > 0 else 0
        rr_tp2 = abs(tp2 - entry_price) / sl_distance if sl_distance > 0 else 0
        rr_tp3 = abs(tp3 - entry_price) / sl_distance if sl_distance > 0 else 0

        # Determine pip size for pip count
        symbol_upper = symbol.upper().replace("/", "").replace("_", "")
        if market == "FOREX":
            pip_size = 0.01 if "JPY" in symbol_upper else 0.0001
            sl_pips = sl_distance / pip_size
        else:
            sl_pips = None

        return RiskCalculation(
            symbol=symbol,
            market=market,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            tp1=tp1,
            tp2=tp2,
            tp3=tp3,
            lot_size=lot_size,
            risk_amount=risk_amount,
            risk_pct=self.risk_per_trade_pct,
            sl_pips=sl_pips,
            sl_distance=sl_distance,
            rr_ratio_tp1=round(rr_tp1, 2),
            rr_ratio_tp2=round(rr_tp2, 2),
            rr_ratio_tp3=round(rr_tp3, 2),
            approved=True,
        )

    def _reject(
        self,
        symbol: str,
        market: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        reason: str,
    ) -> RiskCalculation:
        logger.warning(f"[{symbol}] Trade rejected: {reason}")
        return RiskCalculation(
            symbol=symbol,
            market=market,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            tp1=0.0,
            tp2=0.0,
            tp3=0.0,
            lot_size=0.0,
            risk_amount=0.0,
            risk_pct=0.0,
            sl_pips=None,
            sl_distance=abs(entry_price - stop_loss),
            rr_ratio_tp1=0.0,
            rr_ratio_tp2=0.0,
            rr_ratio_tp3=0.0,
            approved=False,
            rejection_reason=reason,
        )

    def trailing_stop(
        self,
        entry_price: float,
        current_price: float,
        current_stop: float,
        atr: float,
        direction: str,
        atr_multiplier: float = 2.0,
    ) -> float:
        """
        ATR-based trailing stop. Only moves in the trade's favour.
        """
        if direction == "LONG":
            proposed = current_price - atr * atr_multiplier
            return max(proposed, current_stop)
        else:
            proposed = current_price + atr * atr_multiplier
            return min(proposed, current_stop)
