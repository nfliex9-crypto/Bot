"""Base execution interface."""
from abc import ABC, abstractmethod
from app.core.models import TradeSignal


class BaseExecutor(ABC):
    """Abstract base for execution adapters."""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to broker. Returns True on success."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from broker."""
        pass

    @abstractmethod
    def place_order(self, signal: TradeSignal, size: float, paper: bool) -> str | None:
        """
        Place order. Returns order_id or None on failure.
        paper=True for paper trading.
        """
        pass

    @abstractmethod
    def close_position(self, order_id: str, paper: bool) -> bool:
        """Close position by order_id."""
        pass

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, count: int):
        """Fetch OHLCV data. Returns DataFrame or None."""
        pass

    @abstractmethod
    def get_balance(self, paper: bool) -> float:
        """Get account balance."""
        pass
