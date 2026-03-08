from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Automated Trading System"
    env: str = "development"
    api_prefix: str = "/api/v1"

    database_url: str = Field(
        default="postgresql+psycopg2://trader:trader@postgres:5432/trading"
    )

    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None

    binance_api_key: str | None = None
    binance_api_secret: str | None = None
    binance_testnet: bool = True

    risk_per_trade: float = 0.0075
    max_drawdown: float = 0.15
    max_trades_per_session: int = 3
    atr_multiplier: float = 1.5
    tp_multipliers: tuple[float, float, float] = (1.0, 2.0, 3.0)
    confidence_threshold: float = 0.55

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
