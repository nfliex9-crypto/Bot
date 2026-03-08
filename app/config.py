import os
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
from enum import Enum


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class MarketType(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "AI Trading Bot"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # Trading mode
    TRADING_MODE: TradingMode = TradingMode.PAPER

    # Database
    DATABASE_URL: str = "postgresql://trader:trading_password@postgres:5432/trading_bot"
    REDIS_URL: str = "redis://redis:6379/0"

    # MetaTrader 5
    MT5_LOGIN: Optional[int] = None
    MT5_PASSWORD: Optional[str] = None
    MT5_SERVER: Optional[str] = "MetaQuotes-Demo"
    MT5_PATH: Optional[str] = None

    # Binance
    BINANCE_API_KEY: Optional[str] = None
    BINANCE_SECRET_KEY: Optional[str] = None
    BINANCE_TESTNET: bool = True

    # Risk Management
    ACCOUNT_BALANCE: float = 3000.0
    RISK_PER_TRADE: float = 0.0075       # 0.75%
    MAX_DRAWDOWN: float = 0.15           # 15%
    MAX_TRADES_PER_SESSION: int = 3

    # Trade Management
    TP1_RATIO: float = 1.0               # 1R
    TP2_RATIO: float = 1.5              # 1.5R
    TP3_RATIO: float = 2.0              # 2R
    BREAKEVEN_AFTER_TP1: bool = True

    # AI Configuration
    MODEL_PATH: str = Field(
        default_factory=lambda: os.environ.get(
            "MODEL_PATH",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "rf_classifier.pkl")
        )
    )
    MIN_CONFIDENCE: float = 0.65
    RETRAIN_INTERVAL_HOURS: int = 24

    # News Filter
    NEWS_API_KEY: Optional[str] = None
    NEWS_FILTER_MINUTES_BEFORE: int = 30
    NEWS_FILTER_MINUTES_AFTER: int = 30

    # Session Filter (UTC hours)
    LONDON_OPEN_UTC: int = 8
    LONDON_CLOSE_UTC: int = 16
    NEW_YORK_OPEN_UTC: int = 13
    NEW_YORK_CLOSE_UTC: int = 21

    # Symbols
    FOREX_SYMBOLS: str = "EURUSD,GBPUSD,USDJPY,USDCHF,AUDUSD,USDCAD,NZDUSD,GBPJPY,EURJPY"
    CRYPTO_SYMBOLS: str = "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,XRPUSDT"

    # Scan intervals
    SCAN_INTERVAL_SECONDS: int = 60
    HEARTBEAT_INTERVAL_SECONDS: int = 30

    # Timeframes
    H1_TIMEFRAME: str = "H1"
    M15_TIMEFRAME: str = "M15"
    M5_TIMEFRAME: str = "M5"

    # Lookback periods
    LOOKBACK_CANDLES: int = 200
    SWING_LOOKBACK: int = 20
    ATR_PERIOD: int = 14

    @property
    def forex_symbol_list(self) -> List[str]:
        return [s.strip() for s in self.FOREX_SYMBOLS.split(",")]

    @property
    def crypto_symbol_list(self) -> List[str]:
        return [s.strip() for s in self.CRYPTO_SYMBOLS.split(",")]

    @property
    def is_live(self) -> bool:
        return self.TRADING_MODE == TradingMode.LIVE

    @property
    def is_paper(self) -> bool:
        return self.TRADING_MODE == TradingMode.PAPER

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
