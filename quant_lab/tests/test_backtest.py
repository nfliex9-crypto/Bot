from __future__ import annotations

from quant_lab.data_layer.adapters.synthetic import SyntheticOHLCVAdapter
from quant_lab.data_layer.ingest import IngestConfig, ingest_ohlcv
from quant_lab.research.backtest.engine import VectorizedBacktester
from quant_lab.research.features.factory import FeatureFactory


def test_vectorized_backtester_outputs_consistent_lengths(tmp_path):
    adapter = SyntheticOHLCVAdapter(seed=9)
    cfg = IngestConfig(
        symbols=["SPY"],
        start="2024-01-01",
        end="2024-09-30",
        interval="1d",
        out_path=str(tmp_path / "ohlcv.parquet"),
    )
    df = ingest_ohlcv(adapter, cfg)
    feats = FeatureFactory().build(df)
    bt = VectorizedBacktester()
    res = bt.run(feats, "test", "alpha_1", "mean_reversion", 0.5, 0.1)
    assert len(res.returns) == len(res.equity_curve)
