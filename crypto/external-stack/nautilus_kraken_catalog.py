"""Native NautilusTrader v2.0.0rc9 Kraken SPOT market-data archival.

Uses upstream LiveNodeConfig + StreamingConfig + ParquetDataCatalog.
This is a read-only feed configuration, NOT a custom exchange client,
not a trading strategy, and not a broker execution route.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from nautilus_trader.adapters.kraken import (
    KrakenDataClientConfig, KrakenDataClientFactory, KrakenProductType,
)
from nautilus_trader.common import Environment
from nautilus_trader.config import LiveNodeConfig, LiveDataEngineConfig
from nautilus_trader.live import LiveNodeBuilder
from nautilus_trader.model import TraderId
from nautilus_trader.persistence import DataCatalogConfig, StreamingConfig

from nautilus_kraken_spot import build_tester_config


def build_catalog_node(root: Path):
    """Construct native *data-only* node and native Parquet streaming writer."""
    root = Path(root).resolve()
    if root == Path("/"):
        raise ValueError("REFUSING_ROOT_AS_DATA_DIRECTORY")
    # These are exclusively dedicated crypto research directories.
    root.mkdir(parents=True, exist_ok=True)
    staging = root / "feather"
    catalog = root / "catalog"
    config = LiveNodeConfig(
        environment=Environment.LIVE,
        trader_id=TraderId.from_str("RESEARCH-001"),
        shutdown_on_error=True,
        data_engine=LiveDataEngineConfig(validate_data_sequence=True),
        streaming=StreamingConfig(
            writer_path=str(staging),
            catalog=DataCatalogConfig(path=str(catalog)),
            promotion_interval_ms=30_000,
            promote_on_close=True,
            delete_feather_after_promotion=False,
        ),
    )
    builder = LiveNodeBuilder.from_config("SENTINEL-CRYPTO-NATIVE-CATALOG", config)
    builder.add_data_client(
        None,
        KrakenDataClientFactory(),
        KrakenDataClientConfig(product_type=KrakenProductType.SPOT),
    )
    node = builder.build()
    node.add_builtin_actor("DataTester", build_tester_config(log_data=False))
    return node


def main():
    parser = argparse.ArgumentParser(description="Native Kraken L2/trade capture to Nautilus Parquet")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--check-config-only", action="store_true")
    args = parser.parse_args()
    node = build_catalog_node(args.data_root)
    if args.check_config_only:
        print("NATIVE_PARQUET_DATA_ONLY_NODE_READY")
        node.dispose()
        return
    node.run()  # until SIGINT/SIGTERM; native Nautilus owns flush/promote on shutdown


if __name__ == "__main__":
    main()
