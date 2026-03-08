"""
Central configuration for the AI Trading Bot.
All settings are loaded from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from enum import Enum


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Market(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"


@dataclass
class MT5Config:
    login: int = int(os.getenv("MT5_LOGIN", "0"))
    password: str = os.getenv("MT5_PASSWORD", "")
    server: str = os.getenv("MT5_SERVER", "")
    path: str = os.getenv("MT5_PATH", "")
    timeout: int = int(os.getenv("MT5_TIMEOUT", "10000"))


@dataclass
class BinanceConfig:
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    testnet: bool = os.getenv("BINANCE_TESTNET", "true").lower() == "true"
    base_url: str = os.getenv(
        "BINANCE_BASE_URL", "https://testnet.binance.vision"
    )
    live_url: str = "https://api.binance.com"


@dataclass
class DatabaseConfig:
    host: str = os.getenv("DB_HOST", "localhost")
    port: int = int(os.getenv("DB_PORT", "5432"))
    name: str = os.getenv("DB_NAME", "trading_bot")
    user: str = os.getenv("DB_USER", "trader")
    password: str = os.getenv("DB_PASSWORD", "trader_pass")

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def sync_url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class RiskConfig:
    account_balance: float = float(os.getenv("ACCOUNT_BALANCE", "3000.0"))
    risk_per_trade: float = float(os.getenv("RISK_PER_TRADE", "0.0075"))
    max_drawdown: float = float(os.getenv("MAX_DRAWDOWN", "0.15"))
    max_trades_per_session: int = int(os.getenv("MAX_TRADES_SESSION", "3"))
    max_correlated_trades: int = int(os.getenv("MAX_CORRELATED", "2"))
    max_daily_loss: float = float(os.getenv("MAX_DAILY_LOSS", "0.05"))


@dataclass
class StrategyConfig:
    htf_timeframe: str = "H1"
    mtf_timeframe: str = "M15"
    ltf_timeframe: str = "M5"

    liquidity_lookback: int = int(os.getenv("LIQ_LOOKBACK", "50"))
    structure_lookback: int = int(os.getenv("STRUCT_LOOKBACK", "30"))
    atr_period: int = int(os.getenv("ATR_PERIOD", "14"))
    atr_multiplier: float = float(os.getenv("ATR_MULTIPLIER", "1.5"))

    tp1_ratio: float = 1.0
    tp2_ratio: float = 1.5
    tp3_ratio: float = 2.0
    breakeven_after_tp1: bool = True

    min_confidence: float = float(os.getenv("MIN_CONFIDENCE", "0.65"))


@dataclass
class SessionConfig:
    london_open: int = 8
    london_close: int = 16
    newyork_open: int = 13
    newyork_close: int = 21
    timezone: str = "UTC"


@dataclass
class NewsConfig:
    api_url: str = os.getenv(
        "NEWS_API_URL", "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    )
    minutes_before: int = int(os.getenv("NEWS_MINUTES_BEFORE", "30"))
    minutes_after: int = int(os.getenv("NEWS_MINUTES_AFTER", "30"))


FOREX_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    "NZDUSD", "USDCHF", "EURGBP", "EURJPY", "GBPJPY",
]

CRYPTO_SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
]


@dataclass
class AppConfig:
    mode: TradingMode = TradingMode(os.getenv("TRADING_MODE", "paper"))
    mt5: MT5Config = field(default_factory=MT5Config)
    binance: BinanceConfig = field(default_factory=BinanceConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    news: NewsConfig = field(default_factory=NewsConfig)
    forex_symbols: list = field(default_factory=lambda: FOREX_SYMBOLS)
    crypto_symbols: list = field(default_factory=lambda: CRYPTO_SYMBOLS)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    api_host: str = os.getenv("API_HOST", "0.0.0.0")
    api_port: int = int(os.getenv("API_PORT", "8000"))


def get_config() -> AppConfig:
    return AppConfig()
