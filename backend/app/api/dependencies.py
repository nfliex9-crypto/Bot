from functools import lru_cache

from app.core.config import get_settings
from app.services.trading_engine import TradingEngine


@lru_cache
def get_trading_engine() -> TradingEngine:
    return TradingEngine(get_settings())
