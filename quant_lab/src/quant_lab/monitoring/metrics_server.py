from __future__ import annotations

from prometheus_client import Gauge, start_http_server

pnl_gauge = Gauge("quant_lab_strategy_pnl", "Strategy PnL", ["strategy"])
drawdown_gauge = Gauge("quant_lab_strategy_drawdown", "Strategy drawdown", ["strategy"])
latency_gauge = Gauge("quant_lab_execution_latency_ms", "Execution latency in ms", ["broker"])


def start_metrics_server(port: int = 8000) -> None:
    start_http_server(port)
