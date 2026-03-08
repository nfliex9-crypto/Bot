from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from core.enums import Direction
from core.models import TradeRecord

logger = logging.getLogger(__name__)


class BaseExecutor(ABC):
    """Abstract executor — implemented by MT5, Binance, and Paper executors."""

    @abstractmethod
    async def open_trade(self, trade: TradeRecord) -> Optional[str]:
        """Open a trade. Returns broker order ID or None on failure."""
        ...

    @abstractmethod
    async def close_trade(self, trade: TradeRecord, reason: str = "") -> bool:
        """Close full position."""
        ...

    @abstractmethod
    async def partial_close(self, trade: TradeRecord, fraction: float) -> bool:
        """Close a fraction of the position (e.g., 0.33 for TP1)."""
        ...

    @abstractmethod
    async def modify_sl(self, trade: TradeRecord, new_sl: float) -> bool:
        """Modify stop loss (for break-even)."""
        ...

    @abstractmethod
    async def get_open_pnl(self, trade: TradeRecord, current_price: float) -> float:
        """Calculate unrealized PnL."""
        ...
