"""
NautilusTrader Backtesting Framework.

This package provides a comprehensive backtesting framework including:
- Engine configuration and execution
- Exchange-specific simulation models
- Data loading from Parquet catalog
- Performance analysis and metrics
- Walk-forward validation
- Statistical significance testing

Example:
    >>> from impl.backtesting import BacktestRunner, BacktestConfig
    >>> from impl.backtesting import WalkForwardAnalyzer, WalkForwardConfig
    >>> from impl.backtesting import monte_carlo_permutation_test

Modules:
    - engine: BacktestRunner with high-level API
    - simulation: Exchange-specific fill and latency models
    - loader: Data loading from Parquet catalog
    - analysis: Performance metrics and statistical tests
    - walkforward: Walk-forward optimization and validation
"""

# Engine exports
from .engine import (
    BacktestConfig,
    BacktestResult,
    BacktestRunner,
    run_backtest,
)

# Simulation exports
from .simulation import (
    ExchangeType,
    ExchangeSimulationConfig,
    VenueSimulationParams,
    EXCHANGE_CONFIGS,
    get_exchange_config,
    create_fill_model,
    create_latency_model,
    create_simulation_models,
)

# Loader exports
from .loader import (
    DataLoadConfig,
    BacktestDataLoader,
)

# Analysis exports
from .analysis import (
    PerformanceMetrics,
    EquityAnalyzer,
    TradeAnalyzer,
    MonteCarloResult,
    BootstrapResult,
    monte_carlo_permutation_test,
    bootstrap_confidence_interval,
    calculate_deflated_sharpe_ratio,
)

# Walk-forward exports
from .walkforward import (
    WalkForwardConfig,
    WalkForwardWindow,
    WalkForwardResult,
    WalkForwardAnalyzer,
    run_walk_forward_analysis,
)

__all__ = [
    # Engine
    "BacktestConfig",
    "BacktestResult",
    "BacktestRunner",
    "run_backtest",
    # Simulation
    "ExchangeType",
    "ExchangeSimulationConfig",
    "VenueSimulationParams",
    "EXCHANGE_CONFIGS",
    "get_exchange_config",
    "create_fill_model",
    "create_latency_model",
    "create_simulation_models",
    # Loader
    "DataLoadConfig",
    "BacktestDataLoader",
    # Analysis
    "PerformanceMetrics",
    "EquityAnalyzer",
    "TradeAnalyzer",
    "MonteCarloResult",
    "BootstrapResult",
    "monte_carlo_permutation_test",
    "bootstrap_confidence_interval",
    "calculate_deflated_sharpe_ratio",
    # Walk-forward
    "WalkForwardConfig",
    "WalkForwardWindow",
    "WalkForwardResult",
    "WalkForwardAnalyzer",
    "run_walk_forward_analysis",
]

__version__ = "0.1.0"
