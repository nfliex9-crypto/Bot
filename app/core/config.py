from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Trading Bot"
    database_url: str = "postgresql+psycopg://trader:trader@db:5432/trading_bot"
    bot_mode: str = "paper"
    bot_enabled_on_startup: bool = True
    loop_interval_seconds: int = 30

    initial_account_balance: float = 3000.0
    risk_per_trade: float = 0.0075
    max_drawdown: float = 0.15
    max_trades_per_session: int = 3
    min_confidence: float = 0.58

    symbols_forex: list[str] = Field(default_factory=lambda: ["EURUSD", "GBPUSD"])
    symbols_crypto: list[str] = Field(default_factory=lambda: ["BTC/USDT", "ETH/USDT"])

    h1_lookback: int = 220
    m15_lookback: int = 180
    m5_lookback: int = 200
    atr_period: int = 14
    swing_window: int = 2
    structure_stop_buffer_atr: float = 0.2
    news_blackout_before_minutes: int = 30
    news_blackout_after_minutes: int = 30
    news_sync_url: str | None = None

    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    binance_testnet: bool = True

    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_path: str | None = None

    model_path: Path = Path("artifacts/random_forest.joblib")

    @field_validator("symbols_forex", "symbols_crypto", mode="before")
    @classmethod
    def split_csv(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.model_path.parent.mkdir(parents=True, exist_ok=True)
    return settings
