# Alpha Discovery Engine — System Architecture

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Module Breakdown](#module-breakdown)
4. [Technology Stack](#technology-stack)
5. [Data Flow](#data-flow)
6. [Python Code Structure](#python-code-structure)
7. [Critical Component Pseudocode](#critical-component-pseudocode)
8. [Deployment Architecture](#deployment-architecture)
9. [Scaling Strategy](#scaling-strategy)
10. [Performance Benchmarks](#performance-benchmarks)

---

## System Overview

The Alpha Discovery Engine is an institutional-grade quantitative research platform that automates the full lifecycle of algorithmic trading strategy development:

**Research Phase:** Data → Features → Strategy Generation → Backtesting → Validation

**Production Phase:** Selection → Portfolio Construction → Risk Management → Execution → Monitoring

The system generates thousands of candidate strategies, subjects them to rigorous statistical validation to eliminate overfitting, constructs diversified multi-strategy portfolios, and deploys them with institutional risk controls.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ALPHA DISCOVERY ENGINE                                   │
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   DATA       │───▶│   FEATURE    │───▶│  STRATEGY    │───▶│  BACKTEST    │   │
│  │  INGESTION   │    │  ENGINEERING │    │  GENERATION  │    │   ENGINE     │   │
│  │              │    │              │    │              │    │              │   │
│  │ • Yahoo      │    │ • Statistical│    │ • Momentum   │    │ • Vectorized │   │
│  │ • Polygon    │    │ • Volatility │    │ • MeanRev    │    │ • Costs      │   │
│  │ • Binance    │    │ • CrossMkt   │    │ • StatArb    │    │ • Slippage   │   │
│  │ • Synthetic  │    │ • Regime     │    │ • ML/Factor  │    │ • Impact     │   │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────┬───────┘   │
│                                                                      │           │
│  ┌──────────────────────────────────────────────────────────────────┐│           │
│  │                     VALIDATION LAYER                             ││           │
│  │  ┌────────────┐  ┌──────────────┐  ┌────────────┐  ┌─────────┐ ││           │
│  │  │ Statistical│  │ Walk-Forward │  │Monte Carlo │  │Overfit  │◀┘│           │
│  │  │ Tests      │  │ + Purged CV  │  │Simulation  │  │Detector │  │           │
│  │  │            │  │              │  │            │  │         │  │           │
│  │  │ •Deflated  │  │ •N-fold WF   │  │ •Bootstrap │  │ •CSCV   │  │           │
│  │  │  Sharpe    │  │ •Purge gap   │  │ •Block BS  │  │ •Regime │  │           │
│  │  │ •P-values  │  │ •Embargo     │  │ •Path sim  │  │ •Stabil │  │           │
│  │  └────────────┘  └──────────────┘  └────────────┘  └─────────┘  │           │
│  └──────────────────────────────────────┬───────────────────────────┘           │
│                                          │                                       │
│  ┌──────────────┐    ┌──────────────┐   │    ┌──────────────┐                   │
│  │  STRATEGY    │◀───┤  PORTFOLIO   │◀──┘    │    RISK      │                   │
│  │  SELECTION   │    │  OPTIMIZER   │───────▶│  MANAGEMENT  │                   │
│  │              │    │              │        │              │                   │
│  │ • Min filter │    │ • Risk Parity│        │ • Position   │                   │
│  │ • Stat test  │    │ • HRP        │        │   sizing     │                   │
│  │ • Robustness │    │ • Kelly      │        │ • Drawdown   │                   │
│  │ • Corr filter│    │ • Max Sharpe │        │ • Kill switch│                   │
│  │ • Ranking    │    │ • Vol target │        │ • VaR / ES   │                   │
│  └──────────────┘    └──────┬───────┘        └──────┬───────┘                   │
│                              │                       │                           │
│  ┌──────────────┐    ┌──────┴───────┐    ┌──────────┴──────┐                   │
│  │  MONITORING  │◀───┤  EXECUTION   │◀───┤    BROKER       │                   │
│  │              │    │   ENGINE     │    │    ADAPTER      │                   │
│  │ • Dashboard  │    │              │    │                 │                   │
│  │ • Anomaly    │    │ • OMS        │    │ • Paper trading │                   │
│  │ • Health     │    │ • TWAP/VWAP  │    │ • IB / Binance  │                   │
│  │ • Alerts     │    │ • Reconcile  │    │ • FIX protocol  │                   │
│  └──────────────┘    └──────────────┘    └─────────────────┘                   │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │                     PIPELINE ORCHESTRATOR                                │   │
│  │  Coordinates all stages • Manages data flow • Error handling • Logging   │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Module Breakdown

### 1. Data Ingestion Pipeline (`alpha_engine/data/`)

| Component | File | Purpose |
|-----------|------|---------|
| **DataIngestionPipeline** | `ingestion.py` | Orchestrates fetching, validation, caching, incremental updates |
| **DataProvider (ABC)** | `providers.py` | Unified interface for all data sources |
| **YahooProvider** | `providers.py` | Yahoo Finance via yfinance |
| **SyntheticProvider** | `providers.py` | GBM with regime switching for research |
| **DataStorage** | `storage.py` | Parquet-based hierarchical store with symbol/timeframe partitioning |

**Key capabilities:**
- Incremental ingestion (only fetches new bars)
- Data quality validation (NaN handling, high/low correction)
- Close price and returns matrix construction
- Multi-timeframe support (1m to 1d)

### 2. Feature Engineering Engine (`alpha_engine/features/`)

| Component | File | Features Generated |
|-----------|------|-------------------|
| **StatisticalFeatures** | `statistical.py` | Z-scores, rank transforms, autocorrelation, Hurst exponent, entropy, rolling beta, information ratio, lagged features |
| **VolatilityFeatures** | `volatility.py` | Parkinson, Garman-Klass, Yang-Zhang estimators, ATR, Bollinger, EWMA vol, variance ratio, vol-of-vol |
| **CrossMarketFeatures** | `cross_market.py` | Lead-lag correlation, relative strength, spread z-score, cointegration residuals, sector momentum, PCA factors |
| **RegimeFeatures** | `regime.py` | HMM regimes, volatility regimes, trend classification, CUSUM breaks, mean-reversion scoring, stress indicators |
| **FeatureFactory** | `factory.py` | Orchestrates all generators, 100+ features per asset |
| **FeatureEngine** | `engine.py` | Feature selection via IC and mutual information, coverage filtering |

**Feature count per asset: ~120 features** including:
- 7 momentum windows × 2 metrics = 14 momentum features
- 3 z-score windows × 3 series = 9 z-score features
- 6 lookback windows × 2 rank metrics = 12 rank features
- 4 vol windows × 5 estimators = 20 volatility features
- 10 lagged return features
- 15+ microstructure features (gap, body ratio, shadows, volume imbalance)
- 10+ regime features
- 20+ cross-asset features

### 3. Strategy Generation Engine (`alpha_engine/strategy/`)

| Component | File | Purpose |
|-----------|------|---------|
| **StrategyGenerator** | `generator.py` | Systematic parameter sweep across all template types |
| **StrategyTemplates** | `templates.py` | Parameterized signal generators for each strategy family |
| **StrategySpec** | `universe.py` | Immutable strategy specification with deterministic fingerprinting |
| **StrategyUniverse** | `universe.py` | Deduplication-aware strategy collection |
| **StrategyEvaluator** | `evaluator.py` | 20+ performance metrics computation |

**Strategy families generated:**

| Family | Method | Typical Count |
|--------|--------|---------------|
| Momentum crossover | MA crossover with smoothing | ~48 |
| Mean reversion | Z-score entry/exit | ~60 |
| Breakout | Donchian channel + ATR | ~48 |
| Volatility regime | Conditional momentum/MR | ~27 |
| Statistical arbitrage | Pairs spread z-score | ~90 per 10 assets |
| Cross-asset momentum | Cross-sectional ranking | ~12 |
| Factor combination | Weighted feature blending | ~500 |
| ML ensemble | Rolling GBM | ~6 |
| Regime switching | Conditional strategy dispatch | ~3 |
| **Total** | | **~700-5000** |

### 4. Backtesting Engine (`alpha_engine/backtest/`)

| Component | File | Purpose |
|-----------|------|---------|
| **BacktestEngine** | `engine.py` | Vectorized simulation with signal dispatch |
| **DefaultCostModel** | `costs.py` | Commission + slippage + sqrt market impact + borrow cost |
| **ExecutionSimulator** | `execution_sim.py` | Partial fills, volume participation limits, latency jitter |
| **BacktestResult** | `results.py` | Returns, equity, costs, metrics container |

**Cost model components:**
```
Total Cost = Commission (2 bps) + Slippage (1 bps) + Impact (0.1 × √participation) + Borrow (50 bps/yr for shorts)
```

### 5. Statistical Validation Engine (`alpha_engine/validation/`)

| Component | File | Tests |
|-----------|------|-------|
| **StatisticalValidator** | `statistical.py` | Sharpe p-value, Deflated Sharpe Ratio, ADF stationarity, profit factor bootstrap |
| **WalkForwardValidator** | `walk_forward.py` | N-split walk-forward, purged k-fold CV with embargo |
| **MonteCarloValidator** | `monte_carlo.py` | Bootstrap resampling, block bootstrap, permutation test, parametric path sim |
| **OverfitDetector** | `overfitting.py` | CSCV probability, regime robustness, return consistency, IS/OOS degradation |

**Anti-overfitting measures:**
1. **Deflated Sharpe Ratio** — Adjusts for multiple testing (Bailey & Lopez de Prado, 2014)
2. **Purged K-Fold** — Temporal gap between train/test prevents leakage
3. **CSCV** — Combinatorially Symmetric Cross-Validation estimates overfit probability
4. **Monte Carlo** — Bootstrap distribution must have 95th percentile Sharpe > 0
5. **Walk-Forward** — OOS Sharpe must be ≥ 60% of IS Sharpe across folds

### 6. Strategy Selection (`alpha_engine/selection/`)

Five-stage filter funnel:

```
Stage 1: Minimum Filter     — Sharpe ≥ 1.5, Sortino ≥ 2.0, MaxDD ≤ 15%, PF ≥ 1.5
Stage 2: Statistical Tests   — Deflated Sharpe significant, ADF stationary
Stage 3: Robustness          — Monte Carlo passes, overfit score < 0.5
Stage 4: Correlation Filter  — Max pairwise correlation < 0.5
Stage 5: Composite Ranking   — 35% Sharpe + 20% Sortino + 15% Calmar + 15% DD + 15% PF
```

### 7. Portfolio Construction (`alpha_engine/portfolio/`)

| Component | File | Purpose |
|-----------|------|---------|
| **PortfolioOptimizer** | `optimizer.py` | Constructs constrained portfolios with vol targeting |
| **CapitalAllocator** | `allocation.py` | 7 allocation methods: risk parity, HRP, Kelly, max Sharpe, min variance, inverse vol, equal weight |
| **CorrelationAnalyzer** | `correlation.py` | Shrunk correlation, hierarchical clustering, diversification ratio, MCR |

**Constraints enforced:**
- Max gross leverage: 3.0×
- Max net leverage: 1.0×
- Max single strategy: 15%
- Min strategy weight: 2%
- Target portfolio volatility: 10%

### 8. Risk Management (`alpha_engine/risk/`)

| Component | File | Purpose |
|-----------|------|---------|
| **RiskManager** | `manager.py` | Orchestrates all risk controls, VaR/ES, stress testing |
| **ExposureLimits** | `limits.py` | Gross/net/position exposure enforcement |
| **DrawdownController** | `drawdown.py` | Graduated position scaling: 100% → 75% → 50% → 25% → 0% |
| **KillSwitch** | `kill_switch.py` | Emergency halt on DD breach, daily loss, consecutive losses, vol spike |

**Kill switch triggers:**
- Portfolio drawdown ≥ 5%
- Daily loss ≥ 3%
- 10 consecutive losing days
- Volatility spike > 5× baseline
- Connectivity loss

### 9. Execution Engine (`alpha_engine/execution/`)

| Component | File | Purpose |
|-----------|------|---------|
| **ExecutionEngine** | `engine.py` | Rebalance orchestration with risk integration |
| **OrderManager** | `order_manager.py` | Full OMS: create, submit, fill, cancel, reconcile |
| **BrokerAdapter** | `broker_adapter.py` | Abstract broker interface |
| **PaperBroker** | `broker_adapter.py` | Realistic paper trading with fill simulation |

### 10. Monitoring (`alpha_engine/monitoring/`)

| Component | File | Purpose |
|-----------|------|---------|
| **PerformanceDashboard** | `dashboard.py` | NAV tracking, MTD/YTD returns, rolling Sharpe, strategy attribution |
| **AnomalyDetector** | `anomaly.py` | Z-score anomaly detection on returns, vol, Sharpe, drawdown |
| **StrategyHealthMonitor** | `health.py` | Per-strategy health: HEALTHY → DEGRADED → CRITICAL → HALTED |

---

## Technology Stack

### Core

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Python 3.11+ | Ecosystem breadth, NumPy/pandas performance |
| Numerical | NumPy, SciPy | Vectorized computation, statistical tests |
| Data frames | pandas | Time series manipulation, resampling |
| ML | scikit-learn | Feature selection, gradient boosting |
| Statistics | statsmodels | ADF test, econometric models |
| Storage | Parquet (PyArrow) | Columnar compression, fast I/O |

### Production Extensions

| Component | Technology | Purpose |
|-----------|-----------|---------|
| API | FastAPI | REST endpoints for control & monitoring |
| Database | PostgreSQL + TimescaleDB | Trade storage, time-series metrics |
| Cache | Redis | Real-time state, pub/sub alerts |
| Queue | Celery / Ray | Distributed backtesting |
| Monitoring | Prometheus + Grafana | Metrics collection, dashboards |
| Containers | Docker + Kubernetes | Orchestration, scaling |
| CI/CD | GitHub Actions | Automated testing, deployment |

### Optional HMM / Deep Learning

| Component | Technology | Purpose |
|-----------|-----------|---------|
| HMM | hmmlearn | Regime detection |
| Deep Learning | PyTorch | LSTM/Transformer signal models |
| Optimization | cvxpy | Convex portfolio optimization |
| Broker | ib_insync | Interactive Brokers API |

---

## Data Flow

```
                    RAW MARKET DATA
                         │
                    ┌────┴────┐
                    │  INGEST │  Yahoo / Polygon / Synthetic
                    └────┬────┘
                         │  OHLCV DataFrames (Parquet cache)
                    ┌────┴────┐
                    │ FEATURES│  120+ features per asset
                    └────┬────┘
                         │  Feature matrices
                    ┌────┴────┐
                    │GENERATE │  700-5000 candidate strategies
                    └────┬────┘
                         │  StrategySpec objects
                    ┌────┴────┐
                    │BACKTEST │  Vectorized P&L simulation
                    └────┬────┘
                         │  BacktestResult (returns, equity, metrics)
              ┌──────────┴──────────┐
              │                     │
         ┌────┴────┐         ┌─────┴─────┐
         │VALIDATE │         │  SELECT   │
         └────┬────┘         └─────┬─────┘
              │  5-stage filter    │
              └──────────┬─────────┘
                         │  10-30 validated strategies
                    ┌────┴────┐
                    │PORTFOLIO│  Optimal weights
                    └────┬────┘
                         │  Target positions
              ┌──────────┴──────────┐
              │                     │
         ┌────┴────┐         ┌─────┴─────┐
         │  RISK   │         │  EXECUTE  │
         └────┬────┘         └─────┬─────┘
              │                     │
              └──────────┬──────────┘
                    ┌────┴────┐
                    │ MONITOR │  Dashboards, alerts, health
                    └─────────┘
```

---

## Python Code Structure

```
alpha_engine/
├── __init__.py                 # Package metadata
├── config.py                   # EngineConfig with all sub-configs
├── run_pipeline.py             # CLI entry point
│
├── data/                       # Market Data Ingestion
│   ├── __init__.py
│   ├── ingestion.py            # DataIngestionPipeline
│   ├── providers.py            # DataProvider, YahooProvider, SyntheticProvider
│   └── storage.py              # DataStorage (Parquet)
│
├── features/                   # Feature Engineering
│   ├── __init__.py
│   ├── engine.py               # FeatureEngine (orchestrator)
│   ├── factory.py              # FeatureFactory (bulk generation)
│   ├── statistical.py          # StatisticalFeatures
│   ├── volatility.py           # VolatilityFeatures
│   ├── cross_market.py         # CrossMarketFeatures
│   └── regime.py               # RegimeFeatures
│
├── strategy/                   # Strategy Generation
│   ├── __init__.py
│   ├── generator.py            # StrategyGenerator
│   ├── templates.py            # StrategyTemplates (signal logic)
│   ├── universe.py             # StrategySpec, StrategyUniverse
│   └── evaluator.py            # StrategyEvaluator, PerformanceMetrics
│
├── backtest/                   # Backtesting
│   ├── __init__.py
│   ├── engine.py               # BacktestEngine (vectorized)
│   ├── costs.py                # CostModel, DefaultCostModel
│   ├── execution_sim.py        # ExecutionSimulator
│   └── results.py              # BacktestResult
│
├── validation/                 # Statistical Validation
│   ├── __init__.py
│   ├── statistical.py          # StatisticalValidator (deflated Sharpe, p-values)
│   ├── walk_forward.py         # WalkForwardValidator (purged k-fold)
│   ├── monte_carlo.py          # MonteCarloValidator (bootstrap, permutation)
│   └── overfitting.py          # OverfitDetector (CSCV, regime robustness)
│
├── selection/                  # Strategy Selection
│   ├── __init__.py
│   └── selector.py             # StrategySelector (5-stage funnel)
│
├── portfolio/                  # Portfolio Construction
│   ├── __init__.py
│   ├── optimizer.py            # PortfolioOptimizer
│   ├── allocation.py           # CapitalAllocator (7 methods)
│   └── correlation.py          # CorrelationAnalyzer
│
├── risk/                       # Risk Management
│   ├── __init__.py
│   ├── manager.py              # RiskManager (orchestrator)
│   ├── limits.py               # ExposureLimits
│   ├── drawdown.py             # DrawdownController
│   └── kill_switch.py          # KillSwitch
│
├── execution/                  # Live Execution
│   ├── __init__.py
│   ├── engine.py               # ExecutionEngine
│   ├── order_manager.py        # OrderManager, Order
│   └── broker_adapter.py       # BrokerAdapter, PaperBroker
│
├── monitoring/                 # Monitoring
│   ├── __init__.py
│   ├── dashboard.py            # PerformanceDashboard
│   ├── anomaly.py              # AnomalyDetector
│   └── health.py               # StrategyHealthMonitor
│
└── pipeline/                   # Orchestration
    ├── __init__.py
    └── orchestrator.py         # AlphaDiscoveryPipeline
```

---

## Critical Component Pseudocode

### Pipeline Orchestration

```
FUNCTION run_pipeline(symbols, provider):
    data = ingest_market_data(symbols, provider)          # Stage 1
    features = generate_features(data)                     # Stage 2
    universe = generate_strategies(symbols, features)      # Stage 3
    results = backtest_all(universe, data, features)        # Stage 4

    FOR each result in results:                             # Stage 5
        IF NOT passes_minimum_filter(result): DISCARD
        IF NOT passes_statistical_test(result, n_total): DISCARD
        IF NOT passes_monte_carlo(result): DISCARD
        IF is_overfit(result): DISCARD
    END FOR

    selected = remove_correlated(surviving, max_corr=0.5)  # Diversification
    ranked = rank_by_composite_score(selected)

    portfolio = optimize_portfolio(ranked[:30])             # Stage 6
    portfolio = apply_vol_target(portfolio, target=10%)
    portfolio = enforce_constraints(portfolio)

    DEPLOY(portfolio)                                       # Stage 7
```

### Deflated Sharpe Ratio

```
FUNCTION deflated_sharpe(observed_SR, returns, n_trials):
    n = length(returns)
    skew = skewness(returns)
    kurt = kurtosis(returns)

    # Expected maximum Sharpe from n_trials noise strategies
    E_max_SR = (1 - γ) × Φ⁻¹(1 - 1/n_trials) + γ × Φ⁻¹(1 - 1/(n_trials × e))
    E_max_SR = E_max_SR × √(252/n)

    # Standard error accounting for non-normality
    SE = √((1 - skew × SR + (kurt-1)/4 × SR²) / (n-1))

    DSR = (observed_SR - E_max_SR) / SE
    RETURN DSR
```

### Walk-Forward with Purged K-Fold

```
FUNCTION purged_kfold(returns, n_folds, purge_days, embargo_days):
    fold_size = length(returns) / n_folds
    results = []

    FOR fold in 0..n_folds:
        test_start = fold × fold_size
        test_end = (fold + 1) × fold_size

        # Purge: remove data near test boundaries from training
        purge_start = test_start - purge_days
        embargo_end = test_end + embargo_days

        train = returns[NOT in purge_start..embargo_end]
        test = returns[test_start..test_end]

        is_sharpe = compute_sharpe(train)
        oos_sharpe = compute_sharpe(test)
        results.append((is_sharpe, oos_sharpe))

    RETURN results
```

### Risk-Parity Allocation

```
FUNCTION risk_parity(covariance_matrix):
    n = dimensions(covariance_matrix)
    w = equal_weights(n)

    REPEAT until convergence:
        portfolio_variance = w' × Σ × w
        marginal_risk = Σ × w
        risk_contribution = w ⊙ marginal_risk
        target_risk = portfolio_variance / n

        w_new = w × (target_risk / risk_contribution)
        w_new = w_new / sum(w_new)      # Normalize

        IF max(|w_new - w|) < tolerance: BREAK
        w = w_new

    RETURN w
```

### Kill Switch Logic

```
FUNCTION check_kill_switch(state):
    IF portfolio_drawdown ≥ 5%:
        TRIGGER("max_drawdown_breached")
        LIQUIDATE_ALL_POSITIONS()

    IF daily_loss ≥ 3%:
        TRIGGER("max_daily_loss")
        LIQUIDATE_ALL_POSITIONS()

    IF consecutive_losses ≥ 10:
        TRIGGER("consecutive_loss_limit")
        LIQUIDATE_ALL_POSITIONS()

    IF current_volatility > 5 × baseline_volatility:
        TRIGGER("volatility_spike")
        REDUCE_POSITIONS(75%)

    NOTIFY_ALL_CALLBACKS(event)
```

---

## Deployment Architecture

### Development / Research

```
┌────────────────────────────────────────┐
│         Developer Workstation          │
│                                        │
│  python -m alpha_engine.run_pipeline   │
│        --mode demo                     │
│        --provider synthetic            │
│                                        │
│  Data: Local Parquet files             │
│  Broker: PaperBroker (in-process)      │
└────────────────────────────────────────┘
```

### Staging / Paper Trading

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Pipeline │  │ Postgres │  │  Redis   │  │ Grafana  │   │
│  │  Worker  │  │ + Timesc │  │          │  │          │   │
│  │          │  │          │  │          │  │          │   │
│  │ FastAPI  │  │  Trades  │  │ State    │  │ Dashbd   │   │
│  │ + Engine │  │  Metrics │  │ Cache    │  │ Alerts   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                              │
│  Data: Yahoo Finance / Polygon API                           │
│  Broker: PaperBroker with live prices                        │
└─────────────────────────────────────────────────────────────┘
```

### Production

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                               │
│                                                                      │
│  ┌──────────────────────┐    ┌──────────────────────┐               │
│  │   Research Pod (GPU)  │    │   Execution Pod       │               │
│  │                       │    │                       │               │
│  │  • Strategy generation│    │  • Order management   │               │
│  │  • Backtesting        │    │  • Broker connection  │               │
│  │  • ML training        │    │  • Fill reconciliation│               │
│  │  • Validation         │    │  • Latency < 100ms    │               │
│  └───────────┬───────────┘    └───────────┬───────────┘               │
│              │                             │                          │
│  ┌───────────┴───────────┐    ┌───────────┴───────────┐              │
│  │   Risk Pod             │    │   Monitoring Pod       │              │
│  │                        │    │                        │              │
│  │  • Real-time risk      │    │  • Prometheus          │              │
│  │  • Kill switch         │    │  • Grafana dashboards  │              │
│  │  • Position limits     │    │  • Alertmanager        │              │
│  │  • Stress testing      │    │  • Log aggregation     │              │
│  └────────────────────────┘    └────────────────────────┘              │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────┐         │
│  │                  Data Layer                               │         │
│  │  TimescaleDB │ Redis Cluster │ S3 (Parquet) │ Kafka      │         │
│  └─────────────────────────────────────────────────────────┘         │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Scaling Strategy

### Research Scaling (High-Frequency Research)

| Challenge | Solution | Throughput |
|-----------|----------|------------|
| **Backtest throughput** | Ray/Dask distributed backtesting | 10,000+ strategies/hour |
| **Feature computation** | Vectorized NumPy, Numba JIT | 1M bars/second |
| **ML training** | GPU-accelerated (PyTorch/XGBoost) | 100× speedup |
| **Data I/O** | Parquet with partitioning + memory mapping | 1GB/s read |
| **Parameter sweeps** | Optuna/Ray Tune hyperparameter search | 1000s of configs |

### Execution Scaling

| Challenge | Solution | Target |
|-----------|----------|--------|
| **Order latency** | Co-located servers, FIX protocol | < 10ms |
| **Throughput** | Async order submission | 1000 orders/sec |
| **Reliability** | Active-passive failover | 99.99% uptime |
| **State** | Redis for hot state, Postgres for persistence | < 1ms reads |

### Horizontal Scaling Architecture

```
                    ┌─────────────┐
                    │  Load       │
                    │  Balancer   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────┴────┐ ┌────┴────┐ ┌────┴────┐
         │Research │ │Research │ │Research │    ← Scale out for
         │Worker 1 │ │Worker 2 │ │Worker N │      more strategies
         └────┬────┘ └────┬────┘ └────┬────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────┴──────┐
                    │ Strategy    │    ← Single point for
                    │ Registry    │      consistency
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────┴────┐ ┌────┴────┐ ┌────┴────┐
         │Execution│ │Execution│ │Execution│    ← Scale out for
         │Shard 1  │ │Shard 2  │ │Shard N  │      more assets
         └─────────┘ └─────────┘ └─────────┘
```

---

## Performance Benchmarks

Results from the demo pipeline run (8 synthetic assets, 750 days):

| Metric | Value |
|--------|-------|
| Data ingestion | 0.05s (8 symbols) |
| Feature engineering | 5.7s (121 features × 8 symbols) |
| Strategy generation | 0.06s (713 unique strategies) |
| Backtesting | 31.9s (686 strategies evaluated) |
| Selection pipeline | 150.8s (686 → 256 → 237 → 92 → 13 → 10) |
| Portfolio optimization | 0.01s |
| **Total pipeline** | **188.5s** |
| **Portfolio Sharpe** | **2.79** |
| **Portfolio volatility** | **3.3%** |
| **Diversification ratio** | **2.44** |

---

## Configuration Reference

All configuration is centralized in `alpha_engine/config.py` via the `EngineConfig` dataclass:

```python
from alpha_engine.config import EngineConfig
config = EngineConfig()              # All defaults
config = EngineConfig.from_env()     # From environment variables
```

Key environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ADE_INITIAL_CAPITAL` | 10,000,000 | Starting capital |
| `ADE_COMMISSION_BPS` | 2.0 | Commission in basis points |
| `ADE_SLIPPAGE_BPS` | 1.0 | Slippage in basis points |
| `ADE_TRADING_MODE` | paper | paper / live / research |
| `ADE_BROKER` | interactive_brokers | Broker selection |
| `ADE_KILL_SWITCH_DD` | 0.05 | Kill switch drawdown threshold |
