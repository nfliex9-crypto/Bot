from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class StopMethod(StrEnum):
    ATR = "atr"
    STRUCTURE = "structure"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    app_name: str = "AI Automated Trading Bot"
    environment: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://postgres:postgres@postgres:5432/trading_bot"
    model_store_path: Path = Path("data/confidence_model.joblib")

    mode: TradingMode = TradingMode.PAPER
    stop_method: StopMethod = StopMethod.ATR
    bot_enabled: bool = True
    cycle_interval_seconds: int = 60

    account_balance: float = 3000.0
    risk_per_trade: float = 0.0075
    max_drawdown: float = 0.15
    max_trades_per_session: int = 3
    max_concurrent_trades: int = 4
    confidence_threshold: float = 0.58

    london_session_start_utc: int = 7
    london_session_end_utc: int = 11
    new_york_session_start_utc: int = 13
    new_york_session_end_utc: int = 17

    news_block_window_minutes: int = 30
    high_impact_news_url: str | None = None
    high_impact_news_api_key: str | None = None

    forex_symbols: list[str] = Field(default_factory=lambda: ["EURUSD", "GBPUSD", "USDJPY"])
    crypto_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])

    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_path: str | None = None

    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    binance_testnet: bool = True

    default_exchange_timezone: Literal["UTC"] = "UTC"

    @property
    def risk_amount(self) -> float:
        return self.account_balance * self.risk_per_trade

    @property
    def max_drawdown_amount(self) -> float:
        return self.account_balance * self.max_drawdown
