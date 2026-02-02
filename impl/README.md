# NautilusTrader Implementation Module

A comprehensive trading infrastructure built on NautilusTrader, providing data ingestion, backtesting, quantitative validation, and deployment capabilities.

## Module Structure

```
impl/
├── data/                 # Data ingestion and catalog management
│   ├── catalog.py        # Parquet catalog management
│   ├── download.py       # Batch download with resume capability
│   ├── tardis.py         # Tardis Machine API integration
│   ├── wranglers.py      # Data transformation wranglers
│   ├── symbols.py        # Symbol/instrument ID utilities
│   └── cli.py            # Command-line interface
│
├── backtesting/          # Backtesting infrastructure
│   ├── engine.py         # BacktestRunner wrapper
│   ├── loader.py         # Data loader from catalog
│   ├── simulation.py     # Exchange simulation models
│   ├── walkforward.py    # Walk-forward analysis
│   └── analysis.py       # Performance metrics, Monte Carlo, Bootstrap
│
├── validation/           # Quantitative validation
│   ├── stationarity.py   # ADF, Hurst exponent, half-life tests
│   ├── regime.py         # Regime detection (Simple + HMM)
│   └── validator.py      # Complete validation pipeline
│
├── deployment/           # 5-stage deployment modes
│   ├── modes.py          # Deployment mode definitions
│   ├── dry_run.py        # Dry-run order tracking
│   ├── shadow.py         # Shadow trading simulation
│   ├── validators.py     # Deployment readiness checks
│   └── circuit_breaker.py # Risk controls and emergency stops
│
├── strategies/           # Strategy implementations
│   ├── base.py           # BaseStrategy class
│   ├── ema_cross.py      # EMA Cross strategy
│   ├── market_making.py  # Market Making strategy
│   ├── pairs_trading.py  # Pairs Trading strategy
│   ├── signals.py        # Signal generators
│   └── risk.py           # Risk management utilities
│
└── config/               # Configuration utilities
    └── node.py           # TradingNode configuration
```

## Installation

### Basic Installation

```bash
pip install nautilus_trader numpy
```

### Development Installation

```bash
pip install nautilus_trader numpy pandas
pip install pytest pytest-asyncio mypy ruff statsmodels hmmlearn scipy
```

### Using Makefile

```bash
make install      # Basic installation
make install-dev  # With dev dependencies
make env-check    # Verify environment
```

## Quick Start

### 1. Download Historical Data

```python
from impl.data import download_historical_data

jobs = download_historical_data(
    exchanges=["binance-futures"],
    symbols=["BTCUSDT", "ETHUSDT"],
    start_date="2024-01-01",
    end_date="2024-01-31",
    catalog_path="data/catalog",
)
```

Or via CLI:

```bash
python -m impl.data.cli download \
    --symbol BTCUSDT \
    --start 2024-01-01 \
    --end 2024-12-31 \
    --exchange binance-futures
```

### 2. Run Backtest

```python
from impl.backtesting import BacktestRunner, BacktestConfig
from impl.strategies import EMACrossStrategy

config = BacktestConfig(
    catalog_path="data/catalog",
    venue="BINANCE",
    instrument_ids=["BTCUSDT-PERP.BINANCE"],
    starting_balance=100_000.0,
)

runner = BacktestRunner(config)
runner.setup()
runner.add_strategy(EMACrossStrategy())
runner.add_data()

result = runner.run()
print(result.summary())
```

### 3. Validate Strategy

```python
from impl.validation import validate_strategy, ValidationConfig

config = ValidationConfig(
    min_sharpe=0.5,
    min_trades=100,
    max_drawdown=0.20,
)

result = validate_strategy(
    equity_curve=equity_values,
    returns=returns,
    config=config,
)

print(result.summary())
print(f"Overall Score: {result.overall_score:.2f}")
print(f"Passed: {result.passed}")
```

### 4. Deploy Strategy

```python
from impl.deployment import (
    DeploymentMode,
    DryRunOrderTracker,
    ShadowOrderTracker,
    CircuitBreaker,
    CircuitBreakerConfig,
)

# Stage 1: Dry-Run
tracker = DryRunOrderTracker()
order = tracker.track_order(
    instrument_id="BTCUSDT-PERP.BINANCE",
    side="BUY",
    quantity=0.1,
    order_type="MARKET",
    price=None,
    market_price=50000.0,
)

# Stage 2: Shadow Trading
shadow = ShadowOrderTracker(
    slippage_bps=5.0,
    fill_probability=0.98,
    random_seed=42,  # For reproducibility
)

# Stage 5: Production with Circuit Breaker
circuit_breaker = CircuitBreaker(CircuitBreakerConfig(
    max_daily_loss=5000.0,
    max_drawdown=0.10,
    max_position_value=100_000.0,
))
```

## Makefile Targets

### Setup

| Target | Description |
|--------|-------------|
| `make install` | Install basic dependencies |
| `make install-dev` | Install with dev dependencies |
| `make clean` | Remove build artifacts |
| `make env-check` | Verify environment setup |

### Quality

| Target | Description |
|--------|-------------|
| `make lint` | Run ruff linter |
| `make typecheck` | Run mypy type checker |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make test-coverage` | Run tests with coverage |

### Data

| Target | Description |
|--------|-------------|
| `make data-download SYMBOL=X START=Y END=Z` | Download market data |
| `make data-catalog-info` | Show catalog statistics |
| `make data-validate` | Validate data integrity |

### Backtesting

| Target | Description |
|--------|-------------|
| `make backtest CONFIG=path` | Run backtest |
| `make backtest-walkforward EQUITY=path` | Walk-forward analysis |
| `make backtest-montecarlo RETURNS=path` | Monte Carlo test |

### Validation

| Target | Description |
|--------|-------------|
| `make validate EQUITY=path` | Full strategy validation |
| `make validate-stationarity SERIES=path` | Stationarity tests |
| `make validate-regime RETURNS=path` | Regime detection |

### Deployment

| Target | Description |
|--------|-------------|
| `make dry-run` | Dry-run mode info |
| `make shadow` | Shadow trading mode info |
| `make paper` | Paper trading mode info |
| `make production` | Production checklist |

## Deployment Pipeline

The module implements a 5-stage deployment progression:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  BACKTEST   │ ──▶ │  DRY-RUN    │ ──▶ │   SHADOW    │ ──▶ │   PAPER     │ ──▶ │ PRODUCTION  │
│             │     │             │     │             │     │             │     │             │
│ Historical  │     │ Log orders  │     │ Simulate    │     │ Testnet     │     │ Live        │
│ simulation  │     │ No execute  │     │ fills       │     │ execution   │     │ execution   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
```

### Stage Requirements

| Stage | Requirements |
|-------|--------------|
| **Dry-Run** | Passed backtest, min 100 signals |
| **Shadow** | Passed dry-run, slippage < 0.5% |
| **Paper** | Passed shadow, testnet connectivity |
| **Production** | Passed paper, circuit breaker enabled, risk limits set |

## Quantitative Validation

The validation module provides comprehensive statistical tests:

### 1. Monte Carlo Permutation Test

Tests if strategy returns are statistically significant vs. random.

```python
from impl.backtesting.analysis import monte_carlo_permutation_test

result = monte_carlo_permutation_test(returns, n_permutations=1000)
print(f"P-value: {result.p_value:.4f}")
print(f"Significant: {result.is_significant}")
```

### 2. Bootstrap Confidence Intervals

```python
from impl.backtesting.analysis import bootstrap_confidence_interval

result = bootstrap_confidence_interval(
    returns,
    metric_func=lambda r: np.mean(r) / np.std(r) * np.sqrt(252),
    metric_name="sharpe_ratio",
)
print(f"95% CI: [{result.ci_lower:.2f}, {result.ci_upper:.2f}]")
```

### 3. Deflated Sharpe Ratio

Adjusts for multiple testing / data snooping bias.

```python
from impl.backtesting.analysis import calculate_deflated_sharpe_ratio

dsr = calculate_deflated_sharpe_ratio(
    sharpe=1.5,
    n_trials=100,  # Number of strategies tested
    n_observations=252,
)
print(f"DSR: {dsr:.3f}")  # Probability strategy is skillful
```

### 4. Stationarity Tests (for Stat Arb)

```python
from impl.validation import run_stationarity_tests

result = run_stationarity_tests(spread_series)
print(f"ADF p-value: {result.adf.p_value:.4f}")
print(f"Hurst exponent: {result.hurst.hurst_exponent:.3f}")
print(f"Half-life: {result.half_life.half_life:.1f} periods")
print(f"Stationary: {result.overall_stationary}")
```

### 5. Regime Detection

```python
from impl.validation import SimpleRegimeDetector, analyze_regime_performance

detector = SimpleRegimeDetector()
result = detector.detect_regimes(returns)

print(f"Current regime: {result.current_regime}")
print(f"Transition matrix: {result.transition_matrix}")

# Regime-conditional performance
perf = analyze_regime_performance(returns, result.regime_sequence)
for regime, metrics in perf.items():
    print(f"{regime}: Sharpe={metrics.sharpe_ratio:.2f}")
```

## Configuration Examples

### Backtest Configuration

```yaml
# config/backtest.yaml
trader_id: "BACKTESTER-001"
catalog_path: "data/catalog"
venue: "BINANCE"
instrument_ids:
  - "BTCUSDT-PERP.BINANCE"
  - "ETHUSDT-PERP.BINANCE"
starting_balance: 100000.0
base_currency: "USDT"
account_type: "MARGIN"
log_level: "INFO"
```

### Validation Configuration

```python
ValidationConfig(
    min_sharpe=0.5,           # Minimum Sharpe ratio
    min_trades=100,           # Minimum trade count
    max_drawdown=0.20,        # Maximum 20% drawdown
    min_wfe=0.5,              # Walk-forward efficiency
    monte_carlo_permutations=1000,
    bootstrap_samples=1000,
    significance_level=0.05,
    max_half_life=30.0,       # For stat arb
    n_trials_for_dsr=10,      # Strategies tested
)
```

### Circuit Breaker Configuration

```python
CircuitBreakerConfig(
    max_daily_loss=5000.0,      # Stop if daily loss exceeds
    max_drawdown=0.10,          # Stop at 10% drawdown
    max_position_value=100000.0, # Maximum position size
    max_error_rate=10.0,        # Errors per minute
    cooldown_minutes=60,        # Cooldown before reset
    auto_reset=False,           # Manual reset required
    notify_on_trigger=True,     # Send notifications
)
```

## Testing

```bash
# Run all tests
make test

# Run with coverage
make test-coverage

# Run specific test file
pytest tests/unit/test_validation.py -v

# Type checking
make typecheck

# Linting
make lint
```

## API Reference

### Data Module

| Class/Function | Description |
|----------------|-------------|
| `ParquetCatalogManager` | Manage Parquet data catalog |
| `BatchDownloader` | Parallel data downloads |
| `TardisDownloader` | Tardis Machine API client |
| `TradeTickWrangler` | Transform trade tick data |
| `BarDataWrangler` | Aggregate bars from ticks |
| `download_historical_data()` | Convenience download function |

### Backtesting Module

| Class/Function | Description |
|----------------|-------------|
| `BacktestRunner` | High-level backtest runner |
| `BacktestConfig` | Backtest configuration |
| `BacktestResult` | Backtest results container |
| `BacktestDataLoader` | Load data from catalog |
| `WalkForwardAnalyzer` | Walk-forward analysis |
| `monte_carlo_permutation_test()` | Statistical significance |
| `bootstrap_confidence_interval()` | Confidence intervals |
| `calculate_deflated_sharpe_ratio()` | Adjusted Sharpe |

### Validation Module

| Class/Function | Description |
|----------------|-------------|
| `StrategyValidator` | Complete validation pipeline |
| `ValidationConfig` | Validation parameters |
| `ValidationResult` | Validation results |
| `run_stationarity_tests()` | ADF, Hurst, half-life |
| `SimpleRegimeDetector` | Rolling statistics regime |
| `HMMRegimeDetector` | Hidden Markov Model regime |
| `analyze_regime_performance()` | Regime-conditional metrics |

### Deployment Module

| Class/Function | Description |
|----------------|-------------|
| `DeploymentMode` | Enum of 5 deployment stages |
| `DryRunOrderTracker` | Track dry-run orders |
| `ShadowOrderTracker` | Simulate shadow fills |
| `DeploymentValidator` | Validate deployment readiness |
| `CircuitBreaker` | Risk controls |
| `validate_deployment_readiness()` | Check promotion eligibility |

### Strategies Module

| Class/Function | Description |
|----------------|-------------|
| `BaseStrategy` | Base class for strategies |
| `EMACrossStrategy` | EMA crossover strategy |
| `MarketMakingStrategy` | Market making strategy |
| `PairsTradingStrategy` | Pairs trading strategy |
| `RiskManager` | Risk management utilities |
| `PositionSizer` | Position sizing calculations |

## License

Proprietary - ValidAlpha

## Version

0.1.0
