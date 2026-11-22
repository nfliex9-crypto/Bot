"""Upstream NautilusTrader v2.0.0rc9 DataTester for live Kraken Spot L2/trades.

This is only an instrument and data-adapter configuration of NautilusTrader's
official examples/live/kraken/data_tester.py. No private credentials, custom
exchange protocol, strategy engine, or execution-client registration.
Upstream: https://github.com/nautechsystems/nautilus_trader/blob/v2.0.0rc9/examples/live/kraken/data_tester.py
"""
from __future__ import annotations

from nautilus_trader.adapters.kraken import KrakenDataClientConfig
from nautilus_trader.adapters.kraken import KrakenDataClientFactory
from nautilus_trader.adapters.kraken import KrakenProductType
from nautilus_trader.common import Environment
from nautilus_trader.live import LiveNode
from nautilus_trader.model import ClientId
from nautilus_trader.model import InstrumentId
from nautilus_trader.model import TraderId
from nautilus_trader.testkit import DataTesterConfig


def build_tester_config():
    # Upstream DataTesterConfig defaults subscribe_book_deltas=False.
    # Explicitly subscribe, otherwise manage_book alone DOES NOT produce L2.
    return DataTesterConfig(
        client_id=ClientId.from_str("KRAKEN"),
        instrument_ids=[InstrumentId.from_str("BTC/USD.KRAKEN")],
        subscribe_book_deltas=True,
        book_depth=10,
        subscribe_quotes=True,
        subscribe_trades=True,
        manage_book=True,
        log_data=True,
        stats_interval_secs=5,
    )


def build_readonly_node():
    """Public SPOT book + trades. No execution client means no order route."""
    node = (
        LiveNode.builder(
            "SENTINEL-CRYPTO-READONLY-001",
            TraderId.from_str("RESEARCH-001"),
            Environment.LIVE,  # Market DATA environment only; not a trading account
        )
        .add_data_client(
            None,
            KrakenDataClientFactory(),
            KrakenDataClientConfig(product_type=KrakenProductType.SPOT),
        )
        .build()
    )
    node.add_builtin_actor(
        "DataTester",
        build_tester_config(),
    )
    return node


def main():
    # Official node.run() blocks and logs real data. Ctrl+C to stop.
    build_readonly_node().run()


if __name__ == "__main__":
    main()