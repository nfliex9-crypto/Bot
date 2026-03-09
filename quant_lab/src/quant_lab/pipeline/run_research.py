from __future__ import annotations

from pathlib import Path
import numpy as np
import polars as pl

from quant_lab.common.config import load_yaml
from quant_lab.common.logging import get_logger
from quant_lab.common.types import StrategyThresholds
from quant_lab.data_layer.adapters.synthetic import SyntheticOHLCVAdapter
from quant_lab.data_layer.ingest import IngestConfig, ingest_ohlcv
from quant_lab.data_layer.storage import write_parquet
from quant_lab.portfolio.optimizer import build_portfolio_weights
from quant_lab.research.backtest.engine import VectorizedBacktester
from quant_lab.research.discovery.generator import StrategyGenerator
from quant_lab.research.features.factory import FeatureFactory
from quant_lab.research.registry.strategy_registry import StrategyRecord, StrategyRegistry
from quant_lab.research.validation.validator import validate_returns
from quant_lab.risk.limits import RiskLimits
from quant_lab.risk.risk_manager import RiskManager

LOGGER = get_logger("quant_lab.run_research")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _aggregate_strategy_returns(df: pl.DataFrame, bt: VectorizedBacktester, spec) -> np.ndarray:
    symbols = df.get_column("symbol").unique().to_list()
    per_symbol: list[np.ndarray] = []
    for symbol in symbols:
        sdf = df.filter(pl.col("symbol") == symbol)
        result = bt.run(sdf, spec.name, spec.signal_col, spec.model_type, spec.entry, spec.exit)
        per_symbol.append(result.returns)
    min_len = min(len(x) for x in per_symbol)
    aligned = np.vstack([x[-min_len:] for x in per_symbol])
    return aligned.mean(axis=0)


def main() -> None:
    root = _project_root()
    cfg = load_yaml(root / "configs" / "base.yaml")

    adapter = SyntheticOHLCVAdapter(seed=cfg["seed"])
    ingest_cfg = IngestConfig(
        symbols=cfg["data"]["symbols"],
        start=cfg["data"]["start"],
        end=cfg["data"]["end"],
        interval=cfg["data"]["interval"],
        out_path=str(root / cfg["data"]["bronze_path"]),
    )
    ohlcv = ingest_ohlcv(adapter, ingest_cfg)
    LOGGER.info("Ingested rows=%d", ohlcv.height)

    features = FeatureFactory().build(ohlcv)
    write_parquet(features, str(root / cfg["data"]["silver_path"]))
    LOGGER.info("Feature rows=%d cols=%d", features.height, features.width)

    factor_cols = [
        c
        for c in features.columns
        if c.startswith("alpha_") or c.startswith("ret_mean_") or c in {"ret_idio", "hl_spread"}
    ]
    generator = StrategyGenerator(factor_cols=factor_cols)
    strategies = generator.generate()
    LOGGER.info("Generated candidate strategies=%d", len(strategies))

    bt = VectorizedBacktester(
        fee_bps=float(cfg["research"]["fee_bps"]),
        slippage_bps=float(cfg["research"]["slippage_bps"]),
    )
    thresholds = StrategyThresholds(
        sharpe_min=float(cfg["research"]["sharpe_min"]),
        max_drawdown_min=float(cfg["research"]["max_drawdown_min"]),
        profit_factor_min=float(cfg["research"]["profit_factor_min"]),
    )
    registry = StrategyRegistry(path=str(root / cfg["data"]["registry_path"]), thresholds=thresholds)

    passed_returns: list[np.ndarray] = []
    passed_names: list[str] = []
    for spec in strategies:
        strategy_returns = _aggregate_strategy_returns(features, bt, spec)
        report = validate_returns(strategy_returns)
        turnover_proxy = float(np.mean(np.abs(np.diff(np.sign(strategy_returns), prepend=0))))
        record = StrategyRecord(
            name=spec.name,
            signal_col=spec.signal_col,
            model_type=spec.model_type,
            entry=spec.entry,
            exit=spec.exit,
            sharpe=report.sharpe,
            sortino=report.sortino,
            max_drawdown=report.max_drawdown,
            profit_factor=report.profit_factor,
            turnover=turnover_proxy,
            walk_forward_consistency=report.walk_forward_consistency,
            mc_sharpe_p10=report.mc_sharpe_p10,
            mc_mdd_p90=report.mc_mdd_p90,
        )
        saved = registry.register(record)
        if saved.passed:
            passed_returns.append(strategy_returns)
            passed_names.append(saved.name)

    LOGGER.info("Passed strategies=%d", len(passed_returns))
    if not passed_returns:
        LOGGER.warning("No strategy passed the threshold gates.")
        return

    returns_matrix = np.vstack(passed_returns)
    weights = build_portfolio_weights(returns_matrix, target_vol=float(cfg["portfolio"]["target_vol"]))

    portfolio_returns = (weights[:, None] * returns_matrix).sum(axis=0)
    portfolio_equity = np.cumprod(1 + portfolio_returns)
    portfolio_dd = float(np.min(portfolio_equity / np.maximum.accumulate(portfolio_equity) - 1))
    gross = float(np.sum(np.abs(weights)))
    net = float(np.sum(weights))
    max_weight = float(np.max(np.abs(weights)))

    limits = RiskLimits(
        max_gross=float(cfg["risk"]["max_gross"]),
        max_net=float(cfg["risk"]["max_net"]),
        max_symbol_weight=float(cfg["risk"]["max_symbol_weight"]),
        kill_switch_dd=float(cfg["risk"]["kill_switch_dd"]),
    )
    risk_result = RiskManager(limits).check(gross, net, max_weight, portfolio_dd)
    LOGGER.info("Risk gate passed=%s reason=%s", risk_result.passed, risk_result.reason)
    LOGGER.info("Top strategies: %s", ", ".join(passed_names[:5]))


if __name__ == "__main__":
    main()
