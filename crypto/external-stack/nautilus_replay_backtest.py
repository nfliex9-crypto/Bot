"""Research-only NautilusTrader backtest over *recorded* Kraken Spot native L2.

Uses NautilusTrader's own OrderBookImbalance teaching strategy and BacktestEngine.
This is an execution-plumbing check, NOT a validated profitable strategy.
All market prices/deltas/trades must come from native live Parquet catalog.
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path


def run(catalog_dir: Path) -> dict:
    from nautilus_trader.adapters.kraken import KRAKEN_VENUE
    from nautilus_trader.backtest import BacktestEngine
    from nautilus_trader.config import BacktestEngineConfig
    from nautilus_trader.execution import MakerTakerFeeModel
    from nautilus_trader.model import (
        AccountType, BookType, Currency, Money, OmsType, Quantity, TraderId
    )
    from nautilus_trader.persistence import ParquetDataCatalog
    from nautilus_trader.trading import OrderBookImbalanceConfig

    catalog_dir = Path(catalog_dir).resolve(strict=True)
    catalog = ParquetDataCatalog(str(catalog_dir))
    name = "BTC/USD.KRAKEN"
    instruments = [i for i in catalog.instruments() if str(i.id) == name]
    if len(instruments) != 1:
        raise ValueError("MISSING_OR_AMBIGUOUS_AUTHENTIC_KRAKEN_INSTRUMENT")
    instrument = instruments[0]

    trades = catalog.query_trade_ticks(identifiers=[name])
    deltas = catalog.query_order_book_deltas(identifiers=[name])
    if not trades or not deltas:
        raise ValueError("REQUIRES_BOTH_NATIVE_REAL_TRADES_AND_L2")
    if any(str(x.instrument_id) != name for x in [*trades, *deltas]):
        raise ValueError("FOREIGN_MARKET_EVENTS_IN_BACKTEST")
    if any(x.ts_init < 1_700_000_000_000_000_000 for x in [*trades, *deltas]):
        raise ValueError("NON_CONTEMPORARY_OR_UNINITIALIZED_EVENT_TIMESTAMPS")

    engine = BacktestEngine(
        BacktestEngineConfig(trader_id=TraderId.from_str("CRYPTO-REPLAY-001"))
    )
    try:
        engine.add_venue(
            venue=KRAKEN_VENUE,
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            base_currency=None,
            starting_balances=[
                Money(Decimal("10"), Currency.from_str("BTC")),
                Money(Decimal("1000000"), Currency.from_str("USD")),
            ],
            book_type=BookType.L2_MBP,
            # Gross-only technical pipeline, NOT net profitability.
            fee_model=MakerTakerFeeModel(
                maker_rate=Decimal("0"),
                taker_rate=Decimal("0"),
            ),
        )
        engine.add_instrument(instrument)
        engine.add_data(deltas)
        engine.add_data(trades)
        engine.add_builtin_strategy(
            "OrderBookImbalance",
            OrderBookImbalanceConfig(
                instrument_id=instrument.id,
                max_trade_size=Quantity.from_str("0.00010000"),
                trigger_min_size=Decimal("20"),
                trigger_imbalance_ratio=Decimal("0.2"),
                min_seconds_between_triggers=1.0,
                book_type=BookType.L2_MBP,
            ),
        )
        engine.run()
        return {
            "status": "NATIVE_REAL_DATA_BACKTEST_PLUMBING_PASSED",
            "source": "nautilus_trader_2.0.0rc9",
            "venue": "KRAKEN",
            "instrument": name,
            "real_recorded_trade_events": len(trades),
            "real_recorded_orderbook_deltas": len(deltas),
            "test_strategy": "UPSTREAM_ORDER_BOOK_IMBALANCE_EDUCATIONAL_ONLY",
            "prices_from_real_exchange_data": True,
            "starting_balances_are_SIMULATED": True,
            "execution_real": False,
            "profitable_strategy_proven": False,
            "transaction_costs_mode": "GROSS_ONLY",
        }
    finally:
        engine.dispose()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--catalog", required=True, type=Path)
    p.add_argument("--out", type=Path, default=None, help="Machine-readable result JSON")
    args = p.parse_args()
    try:
        report = run(args.catalog)
        code = 0
    except Exception as exc:
        report = {
            "status": "BACKTEST_PLUMBING_NOT_VERIFIED",
            "error_type": type(exc).__name__,
            "error_detail": str(exc)[:400],
            "execution_real": False,
            "profitable_strategy_proven": False,
        }
        code = 1
    line = json.dumps(report, sort_keys=True)
    if args.out is not None:
        args.out.write_text(line + "\n", encoding="utf-8")
    print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
