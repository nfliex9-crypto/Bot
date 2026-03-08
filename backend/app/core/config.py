from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "AI Trading System"
    environment: str = "development"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://trading:trading@db:5432/trading_db"
    database_url_sync: str = "postgresql+psycopg2://trading:trading@db:5432/trading_db"
    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "change-me-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""
    mt5_path: str = ""

    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    risk_per_trade: float = 0.0075
    max_drawdown: float = 0.15
    max_trades_per_session: int = 3

    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
