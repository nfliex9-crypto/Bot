import pandas as pd

from app.config import Settings
from app.strategy.liquidity_bos_pullback import LiquiditySweepBOSPullbackStrategy, StrategyContext


def _df(size: int) -> pd.DataFrame:
    base = [1.0 + i * 0.001 for i in range(size)]
    return pd.DataFrame(
        {
            "time": pd.date_range("2026-01-01", periods=size, freq="5min", tz="UTC"),
            "open": base,
            "high": [x + 0.0004 for x in base],
            "low": [x - 0.0004 for x in base],
            "close": base,
            "volume": [100] * size,
        }
    )


def test_strategy_returns_none_for_insufficient_history():
    strategy = LiquiditySweepBOSPullbackStrategy(Settings())
    signal = strategy.generate_signal(
        StrategyContext(
            market="forex",
            symbol="EURUSD",
            df_h1=_df(30),
            df_m15=_df(30),
            df_m5=_df(30),
        )
    )
    assert signal is None

