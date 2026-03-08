"""
Position Sizer

Calculates optimal position sizes based on account equity, risk per trade,
and stop-loss distance (ATR-based).
"""

from dataclasses import dataclass
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PositionSize:
    lot_size: float
    risk_amount: float
    risk_percent: float
    stop_loss_pips: float
    pip_value: float


class PositionSizer:
    """Calculates position sizes adhering to risk parameters."""

    # Standard pip values for common forex pairs (per standard lot, 100k units)
    FOREX_PIP_VALUES = {
        "EURUSD": 10.0, "GBPUSD": 10.0, "AUDUSD": 10.0, "NZDUSD": 10.0,
        "USDCHF": 10.0, "USDCAD": 10.0, "USDJPY": 7.5, "EURJPY": 7.5,
        "GBPJPY": 7.5, "EURGBP": 12.0, "AUDJPY": 7.5, "CADJPY": 7.5,
    }

    def __init__(self):
        self.settings = get_settings()

    def calculate_forex_position(
        self,
        account_equity: float,
        entry_price: float,
        stop_loss_price: float,
        symbol: str = "EURUSD",
        risk_override: float = None,
    ) -> PositionSize:
        """Calculate forex position size in lots."""
        risk_pct = risk_override or self.settings.risk_per_trade
        risk_amount = account_equity * risk_pct

        sl_distance = abs(entry_price - stop_loss_price)

        is_jpy_pair = symbol.endswith("JPY")
        pip_size = 0.01 if is_jpy_pair else 0.0001
        sl_pips = sl_distance / pip_size

        pip_value = self.FOREX_PIP_VALUES.get(symbol, 10.0)

        if sl_pips == 0:
            logger.warning("Zero stop loss distance", symbol=symbol)
            return PositionSize(0, 0, 0, 0, pip_value)

        lots = risk_amount / (sl_pips * pip_value)
        lots = round(max(0.01, min(lots, 100.0)), 2)

        actual_risk = lots * sl_pips * pip_value
        actual_risk_pct = actual_risk / account_equity if account_equity > 0 else 0

        logger.info(
            "Forex position calculated",
            symbol=symbol, lots=lots, risk_amount=round(actual_risk, 2),
            risk_pct=round(actual_risk_pct * 100, 2), sl_pips=round(sl_pips, 1),
        )

        return PositionSize(
            lot_size=lots,
            risk_amount=round(actual_risk, 2),
            risk_percent=round(actual_risk_pct, 4),
            stop_loss_pips=round(sl_pips, 1),
            pip_value=pip_value,
        )

    def calculate_crypto_position(
        self,
        account_equity: float,
        entry_price: float,
        stop_loss_price: float,
        symbol: str = "BTCUSDT",
        risk_override: float = None,
    ) -> PositionSize:
        """Calculate crypto position size in base asset units."""
        risk_pct = risk_override or self.settings.risk_per_trade
        risk_amount = account_equity * risk_pct

        sl_distance = abs(entry_price - stop_loss_price)
        sl_pct = sl_distance / entry_price if entry_price > 0 else 0

        if sl_distance == 0:
            logger.warning("Zero stop loss distance", symbol=symbol)
            return PositionSize(0, 0, 0, 0, 0)

        position_value = risk_amount / (sl_distance / entry_price)
        quantity = position_value / entry_price

        min_qty = self._get_min_quantity(symbol)
        step_size = self._get_step_size(symbol)
        quantity = max(min_qty, round(quantity / step_size) * step_size)

        actual_risk = quantity * sl_distance
        actual_risk_pct = actual_risk / account_equity if account_equity > 0 else 0

        logger.info(
            "Crypto position calculated",
            symbol=symbol, quantity=quantity, risk_amount=round(actual_risk, 2),
            risk_pct=round(actual_risk_pct * 100, 2),
        )

        return PositionSize(
            lot_size=quantity,
            risk_amount=round(actual_risk, 2),
            risk_percent=round(actual_risk_pct, 4),
            stop_loss_pips=round(sl_distance, 2),
            pip_value=1.0,
        )

    def _get_min_quantity(self, symbol: str) -> float:
        mins = {"BTCUSDT": 0.00001, "ETHUSDT": 0.0001, "BNBUSDT": 0.001}
        return mins.get(symbol, 0.001)

    def _get_step_size(self, symbol: str) -> float:
        steps = {"BTCUSDT": 0.00001, "ETHUSDT": 0.0001, "BNBUSDT": 0.001}
        return steps.get(symbol, 0.001)
