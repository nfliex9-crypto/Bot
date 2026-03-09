from __future__ import annotations

from quant_lab.data_layer.adapters.synthetic import SyntheticOHLCVAdapter
from quant_lab.data_layer.ingest import IngestConfig, ingest_ohlcv
from quant_lab.research.features.factory import FeatureFactory


def test_feature_factory_generates_alpha_columns(tmp_path):
    adapter = SyntheticOHLCVAdapter(seed=7)
    cfg = IngestConfig(
        symbols=["SPY", "QQQ"],
        start="2024-01-01",
        end="2024-06-30",
        interval="1d",
        out_path=str(tmp_path / "ohlcv.parquet"),
    )
    df = ingest_ohlcv(adapter, cfg)
    feats = FeatureFactory().build(df)
    assert "alpha_1" in feats.columns
    assert "alpha_1_v2" in feats.columns
    assert "regime_high_vol" in feats.columns
