"""
Execution Engine — orchestrates order generation, submission,
and fill management for live and paper trading.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from ..config import ExecutionConfig
from ..risk.manager import RiskManager
from .broker_adapter import BrokerAdapter, BrokerFill, PaperBroker
from .order_manager import Order, OrderManager, OrderSide, OrderType

logger = logging.getLogger(__name__)


@dataclass
class ExecutionReport:
    """Summary of a single rebalance execution cycle."""
    timestamp: float = 0.0
    orders_generated: int = 0
    orders_submitted: int = 0
    orders_filled: int = 0
    orders_rejected: int = 0
    total_notional: float = 0.0
    total_commission: float = 0.0
    avg_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    execution_time_ms: float = 0.0
    fills: list[dict] = field(default_factory=list)


class ExecutionEngine:
    """
    Handles the full execution pipeline:
    1. Convert portfolio targets to orders
    2. Apply risk controls
    3. Submit to broker
    4. Track fills and reconcile
    5. Report execution quality
    """

    def __init__(
        self,
        config: Optional[ExecutionConfig] = None,
        broker: Optional[BrokerAdapter] = None,
        risk_manager: Optional[RiskManager] = None,
    ) -> None:
        self.config = config or ExecutionConfig()
        self.broker = broker or PaperBroker()
        self.risk_manager = risk_manager
        self.oms = OrderManager()
        self._execution_history: list[ExecutionReport] = []

    def initialize(self) -> bool:
        """Connect to broker and initialize the execution engine."""
        connected = self.broker.connect()
        if connected:
            logger.info("Execution engine initialized (mode: %s)", self.config.mode.value)
        else:
            logger.error("Failed to connect to broker")
        return connected

    def execute_rebalance(
        self,
        target_positions: dict[str, float],
        current_prices: dict[str, float],
        strategy_id: str = "portfolio",
    ) -> ExecutionReport:
        """
        Execute a portfolio rebalance from current to target positions.

        Applies risk controls, generates orders, submits to broker,
        and reports execution quality.
        """
        start_time = time.time()
        report = ExecutionReport(timestamp=start_time)

        if self.risk_manager:
            nav = self.broker.get_account_value()
            target_positions = self.risk_manager.apply_risk_controls(
                target_positions, nav,
            )

        if isinstance(self.broker, PaperBroker):
            self.broker.set_prices(current_prices)

        orders = self.oms.generate_rebalance_orders(target_positions, strategy_id)
        report.orders_generated = len(orders)

        if not orders:
            return report

        latencies = []
        for order in orders:
            submitted = self.oms.submit_order(order.order_id)
            if not submitted:
                continue
            report.orders_submitted += 1

            for attempt in range(self.config.retry_attempts):
                fill = self.broker.submit_order(order)
                if fill is not None:
                    self.oms.fill_order(
                        order.order_id,
                        fill.filled_quantity,
                        fill.fill_price,
                        fill.commission,
                    )
                    report.orders_filled += 1
                    report.total_notional += fill.filled_quantity * fill.fill_price
                    report.total_commission += fill.commission
                    latencies.append(fill.latency_ms)
                    report.fills.append({
                        "order_id": order.order_id,
                        "symbol": order.symbol,
                        "side": order.side.value,
                        "qty": fill.filled_quantity,
                        "price": fill.fill_price,
                        "latency_ms": fill.latency_ms,
                    })
                    break
                else:
                    report.orders_rejected += 1
                    if attempt < self.config.retry_attempts - 1:
                        time.sleep(self.config.retry_delay_ms / 1000)

        if latencies:
            report.avg_latency_ms = sum(latencies) / len(latencies)
            report.max_latency_ms = max(latencies)

        report.execution_time_ms = (time.time() - start_time) * 1000
        self._execution_history.append(report)

        logger.info(
            "Rebalance: %d/%d filled, $%.0f notional, %.1fms avg latency",
            report.orders_filled, report.orders_generated,
            report.total_notional, report.avg_latency_ms,
        )

        return report

    def get_positions(self) -> dict[str, float]:
        return self.oms.positions

    def get_execution_history(self) -> list[ExecutionReport]:
        return list(self._execution_history)

    def shutdown(self) -> None:
        active = self.oms.active_orders
        for order in active:
            self.oms.cancel_order(order.order_id)
            logger.info("Cancelled active order: %s", order.order_id)
        self.broker.disconnect()
        logger.info("Execution engine shutdown complete")
