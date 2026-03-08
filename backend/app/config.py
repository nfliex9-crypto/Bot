from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "AI Trading System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-this-secret-key-in-production"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://trader:trader_pass@db:5432/trading_db"
    DATABASE_URL_SYNC: str = "postgresql://trader:trader_pass@db:5432/trading_db"

    # Binance
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_TESTNET: bool = True

    # MetaTrader5
    MT5_LOGIN: int = 0
    MT5_PASSWORD: str = ""
    MT5_SERVER: str = ""
    MT5_PATH: str = ""

    # Risk Management
    RISK_PER_TRADE_PCT: float = 0.75
    MAX_DRAWDOWN_PCT: float = 15.0
    MAX_TRADES_PER_SESSION: int = 3
    TP1_RATIO: float = 1.5
    TP2_RATIO: float = 2.5
    TP3_RATIO: float = 4.0

    # Trading Session
    SESSION_START_HOUR: int = 8
    SESSION_END_HOUR: int = 20

    # AI Model
    MODEL_PATH: str = "/app/models/rf_classifier.joblib"
    MIN_CONFIDENCE_THRESHOLD: float = 0.65

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
