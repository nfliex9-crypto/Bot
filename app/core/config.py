from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.models import StopMethod, TradingMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI Trading Bot"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://trader:trader@postgres:5432/trading_bot"

    trading_mode: TradingMode = TradingMode.PAPER
    worker_poll_seconds: int = 60
    confidence_threshold: float = 0.58

    account_balance: float = 3000.0
    risk_per_trade: float = 0.0075
    max_drawdown: float = 0.15
    max_trades_per_session: int = 3

    stop_method: StopMethod = StopMethod.ATR
    atr_period: int = 14
    atr_multiplier: float = 1.5
    structure_buffer_atr: float = 0.15

    london_open_hour: int = 7
    london_close_hour: int = 16
    new_york_open_hour: int = 8
    new_york_close_hour: int = 17
    london_timezone: str = "Europe/London"
    new_york_timezone: str = "America/New_York"

    forex_symbols: list[str] = Field(default_factory=lambda: ["EURUSD", "GBPUSD"])
    crypto_symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    candle_limit: int = 300

    news_filter_enabled: bool = True
    news_feed_url: str = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    news_blackout_minutes_before: int = 30
    news_blackout_minutes_after: int = 30
    news_fail_open: bool = True

    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    binance_testnet: bool = False
    binance_futures: bool = True

    mt5_connection_mode: Literal["bridge", "direct"] = "bridge"
    mt5_bridge_url: str | None = None
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_path: str | None = None

    model_path: Path = Path("runtime/models/random_forest.joblib")
    min_training_samples: int = 40
    max_training_rows: int = 2000

    paper_slippage_bps: float = 2.0
    paper_fee_bps: float = 4.0

    @field_validator("forex_symbols", "crypto_symbols", mode="before")
    @classmethod
    def split_symbols(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return [item.strip().upper() for item in value if item.strip()]
        if not value:
            return []
        return [item.strip().upper() for item in str(value).split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.model_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
