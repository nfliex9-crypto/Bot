"""
Central configuration for the Alpha Discovery Engine.

All parameters governing research pipeline behavior, risk limits,
execution settings, and validation thresholds are defined here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TradingMode(Enum):
    PAPER = "paper"
    LIVE = "live"
    RESEARCH = "research"


class AssetClass(Enum):
    EQUITY = "equity"
    FX = "fx"
    CRYPTO = "crypto"
    FUTURES = "futures"
    OPTIONS = "options"


@dataclass(frozen=True)
class DataConfig:
    providers: list[str] = field(default_factory=lambda: ["yahoo", "polygon", "binance"])
    base_symbols: list[str] = field(default_factory=lambda: [
        "SPY", "QQQ", "IWM", "EFA", "EEM",
        "TLT", "IEF", "HYG", "LQD",
        "GLD", "SLV", "USO", "UNG",
        "UUP", "FXE", "FXY",
        "VIX",
    ])
    crypto_symbols: list[str] = field(default_factory=lambda: [
        "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD",
    ])
    timeframes: list[str] = field(default_factory=lambda: [
        "1m", "5m", "15m", "1h", "4h", "1d",
    ])
    lookback_days: int = 750
    min_history_days: int = 252
    cache_dir: str = "data/cache"
    storage_backend: str = "parquet"


@dataclass(frozen=True)
class FeatureConfig:
    lookback_windows: list[int] = field(default_factory=lambda: [5, 10, 21, 63, 126, 252])
    volatility_windows: list[int] = field(default_factory=lambda: [5, 10, 21, 63])
    momentum_windows: list[int] = field(default_factory=lambda: [1, 5, 10, 21, 63, 126, 252])
    correlation_window: int = 63
    regime_window: int = 126
    max_lag: int = 10
    zscore_windows: list[int] = field(default_factory=lambda: [21, 63, 126])
    rank_normalize: bool = True
    winsorize_pct: float = 0.01
    min_non_null_pct: float = 0.7


@dataclass(frozen=True)
class StrategyConfig:
    n_candidates: int = 5000
    generation_methods: list[str] = field(default_factory=lambda: [
        "momentum", "mean_reversion", "breakout", "statistical_arbitrage",
        "volatility_regime", "cross_asset", "factor_combination",
        "ml_ensemble", "regime_switching",
    ])
    max_holding_period: int = 63
    min_holding_period: int = 1
    signal_decay_halflife: int = 5
    rebalance_frequencies: list[str] = field(default_factory=lambda: ["daily", "weekly"])


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 10_000_000.0
    commission_bps: float = 2.0
    slippage_bps: float = 1.0
    market_impact_model: str = "sqrt"
    fill_probability: float = 0.98
    borrow_cost_bps: float = 50.0
    margin_requirement: float = 0.5
    max_position_pct: float = 0.05
    vectorized: bool = True


@dataclass(frozen=True)
class ValidationConfig:
    min_sharpe: float = 1.5
    min_sortino: float = 2.0
    max_drawdown: float = 0.15
    min_profit_factor: float = 1.5
    min_trades: int = 100
    oos_ratio: float = 0.3
    n_walk_forward_splits: int = 5
    purge_gap_days: int = 5
    embargo_days: int = 2
    n_monte_carlo_sims: int = 1000
    confidence_level: float = 0.95
    max_correlation: float = 0.5
    deflated_sharpe_threshold: float = 0.05
    n_cv_folds: int = 5
    min_oos_sharpe: float = 0.8


@dataclass(frozen=True)
class PortfolioConfig:
    max_strategies: int = 30
    max_gross_leverage: float = 3.0
    max_net_leverage: float = 1.0
    target_volatility: float = 0.10
    max_sector_exposure: float = 0.30
    max_single_strategy_weight: float = 0.15
    min_strategy_weight: float = 0.02
    rebalance_frequency: str = "weekly"
    optimization_method: str = "risk_parity"
    correlation_shrinkage: float = 0.5


@dataclass(frozen=True)
class RiskConfig:
    max_portfolio_drawdown: float = 0.10
    max_strategy_drawdown: float = 0.15
    max_daily_loss: float = 0.02
    max_position_size_pct: float = 0.05
    max_gross_exposure: float = 3.0
    max_net_exposure: float = 1.0
    max_sector_concentration: float = 0.30
    volatility_target: float = 0.10
    volatility_lookback: int = 21
    kill_switch_drawdown: float = 0.05
    kill_switch_daily_loss: float = 0.03
    kill_switch_consecutive_losses: int = 10
    position_limit_per_asset: float = 0.10
    var_confidence: float = 0.99
    var_horizon_days: int = 1
    stress_test_scenarios: list[str] = field(default_factory=lambda: [
        "2008_gfc", "2020_covid", "flash_crash", "rate_shock",
    ])


@dataclass(frozen=True)
class ExecutionConfig:
    mode: TradingMode = TradingMode.PAPER
    broker: str = "interactive_brokers"
    max_order_size_pct: float = 0.02
    twap_slices: int = 10
    vwap_participation_rate: float = 0.05
    max_latency_ms: int = 100
    retry_attempts: int = 3
    retry_delay_ms: int = 500
    heartbeat_interval_s: int = 5
    order_timeout_s: int = 60


@dataclass(frozen=True)
class MonitoringConfig:
    metrics_port: int = 9090
    log_level: str = "INFO"
    alert_channels: list[str] = field(default_factory=lambda: ["log", "email"])
    performance_update_interval_s: int = 60
    anomaly_zscore_threshold: float = 3.0
    health_check_interval_s: int = 30
    metrics_retention_days: int = 365


@dataclass
class EngineConfig:
    """Top-level configuration aggregating all sub-configs."""
    data: DataConfig = field(default_factory=DataConfig)
    features: FeatureConfig = field(default_factory=FeatureConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    @classmethod
    def from_env(cls) -> EngineConfig:
        """Build config from environment variables, falling back to defaults."""
        return cls(
            backtest=BacktestConfig(
                initial_capital=float(os.getenv("ADE_INITIAL_CAPITAL", "10000000")),
                commission_bps=float(os.getenv("ADE_COMMISSION_BPS", "2.0")),
                slippage_bps=float(os.getenv("ADE_SLIPPAGE_BPS", "1.0")),
            ),
            execution=ExecutionConfig(
                mode=TradingMode(os.getenv("ADE_TRADING_MODE", "paper")),
                broker=os.getenv("ADE_BROKER", "interactive_brokers"),
            ),
            risk=RiskConfig(
                kill_switch_drawdown=float(os.getenv("ADE_KILL_SWITCH_DD", "0.05")),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        import dataclasses
        def _convert(obj: Any) -> Any:
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return {k: _convert(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, Enum):
                return obj.value
            return obj
        return _convert(self)
