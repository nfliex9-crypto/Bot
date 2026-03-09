# Quant Lab: Institutional Alpha Discovery Engine

This directory contains a complete, modular quantitative research laboratory for
automatic alpha discovery, validation, and deployment workflows.

## Architecture Diagram

```text
External Sources -> Data Layer -> Feature/Research Engine -> Strategy Discovery
      -> Backtesting -> Statistical Validation -> Strategy Registry
      -> Portfolio Construction -> Risk Engine -> Execution Engine
      -> Monitoring/Observability -> Feedback Loop to Research
```

## Repository Layout

```text
quant_lab/
  configs/
  src/quant_lab/
    data_layer/
    research/
    portfolio/
    risk/
    execution/
    monitoring/
    pipeline/
  tests/
```

## Quickstart

```bash
cd quant_lab
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
quant-lab-research
```

## Run with Docker

```bash
cd quant_lab
docker compose up --build
```

## Research Pipeline

1. Generate synthetic multi-asset OHLCV (or replace adapter with real market source).
2. Normalize and quality-check market data.
3. Generate large feature set and alpha variations.
4. Generate strategy candidates.
5. Backtest with costs/slippage.
6. Validate with risk and robustness metrics.
7. Register robust strategies.
8. Build strategy portfolio and apply risk checks.

## Example Dataset Format

Parquet schema:

- `timestamp` (datetime)
- `symbol` (str)
- `open`, `high`, `low`, `close` (float)
- `volume` (float)
- `ret_1` (float)

## Example Discovered Strategy (registry record)

```json
{
  "name": "mean_reversion_alpha_1_entry0.5_exit0.1",
  "sharpe": 1.71,
  "sortino": 2.04,
  "max_drawdown": -0.12,
  "profit_factor": 1.41,
  "turnover": 0.18,
  "passed": true
}
```

## Production Notes

- Replace `SyntheticOHLCVAdapter` with live adapters (FIX/REST/WebSocket).
- Run research sweeps on distributed workers (Ray/Dask/K8s).
- Expose Prometheus metrics and Grafana dashboards for production monitoring.
