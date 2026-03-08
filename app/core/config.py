from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    trading_mode: TradingMode = TradingMode.PAPER

    # MetaTrader 5
    mt5_login: str = ""
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""

    # Binance
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://trader:trader@localhost:5432/trading_bot"
    database_url_sync: str = "postgresql+psycopg2://trader:trader@localhost:5432/trading_bot"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Risk management
    account_balance: float = 3000.0
    risk_per_trade: float = 0.75
    max_drawdown_pct: float = 15.0
    max_trades_per_session: int = 3

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Symbols
    forex_symbols: List[str] = Field(
        default=["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
    )
    crypto_symbols: List[str] = Field(
        default=["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    )

    # Timeframes
    bias_timeframe: str = "H1"
    structure_timeframe: str = "M15"
    execution_timeframe: str = "M5"

    # News filter
    forex_factory_url: str = (
        "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    )

    # AI
    ml_model_path: str = "ml_models/trade_classifier.joblib"
    min_confidence: float = 0.65

    @property
    def is_paper(self) -> bool:
        return self.trading_mode == TradingMode.PAPER


settings = Settings()
