from app.config import Settings
from app.market.binance_client import BinanceMarketDataClient
from app.market.mt5_client import MT5MarketDataClient


class MarketDataProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.mt5 = MT5MarketDataClient(settings)
        self.binance = BinanceMarketDataClient(settings)

    def get_timeframe_data(self, symbol: str, market_type: str, timeframe: str, bars: int = 300):
        if market_type == "forex":
            return self.mt5.get_ohlcv(symbol, timeframe, bars=bars)
        if market_type == "crypto":
            return self.binance.get_ohlcv(symbol, timeframe, bars=bars)
        raise ValueError(f"Unsupported market type: {market_type}")

