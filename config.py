"""Application configuration with paper/live trading modes."""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Literal


class Settings(BaseSettings):
    """Trading bot configuration."""

    # Mode: paper or live
    TRADING_MODE: Literal["paper", "live"] = Field(default="paper", env="TRADING_MODE")

    # Database (use sqlite:///./trading.db for local dev without PostgreSQL)
    DATABASE_URL: str = Field(
        default="sqlite:///./trading.db",
        env="DATABASE_URL",
    )

    # Risk Management
    ACCOUNT_BALANCE: float = Field(default=3000.0, env="ACCOUNT_BALANCE")
    RISK_PER_TRADE: float = Field(default=0.75, env="RISK_PER_TRADE")  # 0.75%
    MAX_DRAWDOWN: float = Field(default=15.0, env="MAX_DRAWDOWN")  # 15%
    MAX_TRADES_PER_SESSION: int = Field(default=3, env="MAX_TRADES_PER_SESSION")

    # Trade Management
    TP1_R: float = Field(default=1.0, env="TP1_R")
    TP2_R: float = Field(default=1.5, env="TP2_R")
    TP3_R: float = Field(default=2.0, env="TP3_R")

    # MT5
    MT5_LOGIN: int | None = Field(default=None, env="MT5_LOGIN")
    MT5_PASSWORD: str | None = Field(default=None, env="MT5_PASSWORD")
    MT5_SERVER: str | None = Field(default=None, env="MT5_SERVER")
    MT5_PATH: str | None = Field(default=None, env="MT5_PATH")

    # Binance
    BINANCE_API_KEY: str | None = Field(default=None, env="BINANCE_API_KEY")
    BINANCE_API_SECRET: str | None = Field(default=None, env="BINANCE_API_SECRET")
    BINANCE_TESTNET: bool = Field(default=True, env="BINANCE_TESTNET")

    # Redis (for Celery)
    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")

    # API
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="API_PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
