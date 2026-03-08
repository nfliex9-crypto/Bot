from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings


class TradingMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class Settings(BaseSettings):
    # ── Trading Mode ──────────────────────────────────────────────
    trading_mode: TradingMode = TradingMode.PAPER

    # ── MetaTrader 5 ──────────────────────────────────────────────
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = "MetaQuotes-Demo"
    mt5_path: str = ""

    # ── Binance ───────────────────────────────────────────────────
    binance_api_key: str = ""
    binance_api_secret: str = ""
    binance_testnet: bool = True

    # ── PostgreSQL ────────────────────────────────────────────────
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "trading_bot"
    postgres_user: str = "trader"
    postgres_password: str = "secure_password_here"

    # ── Risk Management ───────────────────────────────────────────
    account_balance: float = 3000.0
    risk_per_trade: float = 0.75
    max_drawdown_pct: float = 15.0
    max_trades_per_session: int = 3

    # ── Strategy ──────────────────────────────────────────────────
    htf_timeframe: str = "H1"
    mtf_timeframe: str = "M15"
    ltf_timeframe: str = "M5"

    atr_period: int = 14
    atr_sl_multiplier: float = 1.5
    structure_lookback: int = 20
    liquidity_zone_atr_mult: float = 0.5
    pullback_fib_level: float = 0.618
    min_rr_ratio: float = 1.5
    swing_lookback: int = 10

    tp1_ratio: float = 1.0
    tp2_ratio: float = 1.5
    tp3_ratio: float = 2.0
    breakeven_after_tp1: bool = True

    # ── AI ────────────────────────────────────────────────────────
    ai_min_confidence: float = 0.60
    ai_model_path: str = "models/rf_model.joblib"
    ai_retrain_interval_hours: int = 24

    # ── Sessions (UTC hours) ──────────────────────────────────────
    london_open: int = 7
    london_close: int = 16
    newyork_open: int = 12
    newyork_close: int = 21

    # ── News Filter ───────────────────────────────────────────────
    forex_factory_enabled: bool = True
    news_blackout_minutes: int = 30

    # ── Forex Symbols ─────────────────────────────────────────────
    forex_symbols: List[str] = Field(default=[
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
    ])

    # ── Crypto Symbols ────────────────────────────────────────────
    crypto_symbols: List[str] = Field(default=[
        "BTCUSDT", "ETHUSDT", "SOLUSDT",
    ])

    # ── FastAPI ───────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "change_me_in_production"

    # ── Logging ───────────────────────────────────────────────────
    log_level: str = "INFO"
    base_dir: str = str(Path(__file__).resolve().parent.parent)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
