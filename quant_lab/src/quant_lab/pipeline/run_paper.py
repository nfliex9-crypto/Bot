from __future__ import annotations

from quant_lab.common.logging import get_logger
from quant_lab.execution.oms import OMS, OrderIntent
from quant_lab.execution.paper_broker import PaperBroker

LOGGER = get_logger("quant_lab.run_paper")


def main() -> None:
    broker = PaperBroker()
    oms = OMS(broker)
    order_id = oms.submit_intent(OrderIntent(strategy_id="demo_strategy", symbol="SPY", target_qty=100))
    fill = broker.get_fill(order_id)
    LOGGER.info("Paper order submitted id=%s fill=%s", order_id, fill)
    LOGGER.info("Positions=%s", broker.positions())


if __name__ == "__main__":
    main()
