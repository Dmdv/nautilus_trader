# Backtesting Guide

This guide covers running backtests, walk-forward analysis, and validating strategy performance.

---

## Two API Levels

NautilusTrader provides two backtesting approaches:

| API | Best For | Data Source | Memory Usage |
|-----|----------|-------------|--------------|
| **BacktestEngine** | Research, small datasets | In-memory | High |
| **BacktestNode** | Production, large datasets | Streaming from Parquet | Low |

---

## BacktestEngine (Low-Level API)

Best for interactive research and prototyping.

### Basic Usage

```python
from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money

# 1. Create engine
engine = BacktestEngine(
    config=BacktestEngineConfig(
        trader_id="BACKTESTER-001",
        log_level="INFO",
    )
)

# 2. Add venue
venue = Venue("BINANCE")
engine.add_venue(
    venue=venue,
    oms_type=OmsType.NETTING,
    account_type=AccountType.MARGIN,
    base_currency=None,
    starting_balances=[Money(100_000, USDT)],
)

# 3. Add instrument
engine.add_instrument(instrument)

# 4. Add data
engine.add_data(bars)  # List of Bar objects
# or
engine.add_data(trade_ticks)  # List of TradeTick objects

# 5. Add strategy
config = MyStrategyConfig(
    instrument_id=str(instrument.id),
    bar_type="BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
)
strategy = MyStrategy(config)
engine.add_strategy(strategy)

# 6. Run backtest
engine.run()

# 7. Get results
print(engine.trader.generate_order_fills_report())
print(engine.trader.generate_positions_report())
print(engine.trader.generate_account_report(venue))
```

### With Realistic Simulation

```python
from nautilus_trader.backtest.models import FillModel, LatencyModel

engine.add_venue(
    venue=venue,
    oms_type=OmsType.NETTING,
    account_type=AccountType.MARGIN,
    starting_balances=[Money(100_000, USDT)],

    # Realistic fill model
    fill_model=FillModel(
        prob_fill_on_limit=0.8,      # 80% chance of limit fill
        prob_fill_on_stop=0.9,       # 90% chance of stop fill
        prob_slippage=0.5,           # 50% chance of slippage
        random_seed=42,
    ),

    # Realistic latency
    latency_model=LatencyModel(
        base_latency_nanos=80_000_000,     # 80ms base
        insert_latency_nanos=10_000_000,   # +10ms for inserts
        update_latency_nanos=10_000_000,   # +10ms for updates
        cancel_latency_nanos=10_000_000,   # +10ms for cancels
    ),

    # Execution settings
    reject_stop_orders=False,
    support_gtd_orders=True,
    use_reduce_only=True,
)
```

---

## BacktestNode (High-Level API)

Best for large datasets and production validation.

### Basic Usage

```python
from nautilus_trader.backtest.node import BacktestNode, BacktestVenueConfig
from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    ImportableStrategyConfig,
)

# 1. Configure venue
venue_config = BacktestVenueConfig(
    name="BINANCE",
    oms_type="NETTING",
    account_type="MARGIN",
    starting_balances=["100000 USDT"],
)

# 2. Configure data (streams from Parquet)
data_config = BacktestDataConfig(
    catalog_path="data/catalog",
    data_cls="nautilus_trader.model.data.Bar",
    instrument_id="BTCUSDT-PERP.BINANCE",
    bar_spec="1-MINUTE-LAST",
    start_time="2024-01-01",
    end_time="2024-03-31",
)

# 3. Configure strategy
strategy_config = ImportableStrategyConfig(
    strategy_path="strategies.trend.ema_cross:EMACrossStrategy",
    config_path="strategies.trend.ema_cross:EMACrossConfig",
    config={
        "instrument_id": "BTCUSDT-PERP.BINANCE",
        "bar_type": "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        "fast_period": 10,
        "slow_period": 20,
        "trade_size": "0.01",
    },
)

# 4. Create run configuration
run_config = BacktestRunConfig(
    engine=BacktestEngineConfig(
        trader_id="BACKTEST-001",
        log_level="INFO",
    ),
    venues=[venue_config],
    data=[data_config],
    strategies=[strategy_config],
)

# 5. Run backtest
node = BacktestNode(configs=[run_config])
results = node.run()
```

### Multiple Data Sources

```python
# Multiple instruments
data_configs = [
    BacktestDataConfig(
        catalog_path="data/catalog",
        data_cls="nautilus_trader.model.data.Bar",
        instrument_id="BTCUSDT-PERP.BINANCE",
        bar_spec="1-MINUTE-LAST",
    ),
    BacktestDataConfig(
        catalog_path="data/catalog",
        data_cls="nautilus_trader.model.data.Bar",
        instrument_id="ETHUSDT-PERP.BINANCE",
        bar_spec="1-MINUTE-LAST",
    ),
]

# Order book data
data_configs.append(
    BacktestDataConfig(
        catalog_path="data/catalog",
        data_cls="nautilus_trader.model.data.OrderBookDelta",
        instrument_id="BTCUSDT-PERP.BINANCE",
    )
)
```

---

## Exchange-Specific Simulation

### Binance Futures

```python
BINANCE_SIMULATION = {
    "latency_model": LatencyModel(
        base_latency_nanos=50_000_000,      # 50ms
        insert_latency_nanos=10_000_000,
        update_latency_nanos=10_000_000,
        cancel_latency_nanos=10_000_000,
    ),
    "fill_model": FillModel(
        prob_fill_on_limit=0.85,
        prob_fill_on_stop=0.95,
        prob_slippage=0.4,
        random_seed=42,
    ),
}
```

### Bybit

```python
BYBIT_SIMULATION = {
    "latency_model": LatencyModel(
        base_latency_nanos=60_000_000,      # 60ms
        insert_latency_nanos=15_000_000,
        update_latency_nanos=15_000_000,
        cancel_latency_nanos=15_000_000,
    ),
    "fill_model": FillModel(
        prob_fill_on_limit=0.8,
        prob_fill_on_stop=0.9,
        prob_slippage=0.5,
        random_seed=42,
    ),
}
```

### dYdX

```python
DYDX_SIMULATION = {
    "latency_model": LatencyModel(
        base_latency_nanos=200_000_000,     # 200ms (L2 settlement)
        insert_latency_nanos=50_000_000,
        update_latency_nanos=50_000_000,
        cancel_latency_nanos=50_000_000,
    ),
    "fill_model": FillModel(
        prob_fill_on_limit=0.7,
        prob_fill_on_stop=0.8,
        prob_slippage=0.6,
        random_seed=42,
    ),
    # dYdX-specific
    "gas_cost_per_trade_usd": 0.5,
}
```

---

## Walk-Forward Analysis

Walk-forward validates strategy robustness by training on rolling windows and testing out-of-sample.

### Concept

```
|----Train (90d)----|--Purge (1d)--|--Test (30d)--|
      |----Train (90d)----|--Purge (1d)--|--Test (30d)--|
            |----Train (90d)----|--Purge (1d)--|--Test (30d)--|
```

### Configuration

```python
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class WalkForwardConfig:
    """Walk-forward analysis configuration."""

    # Time windows
    train_period: timedelta = timedelta(days=90)
    test_period: timedelta = timedelta(days=30)
    step_size: timedelta = timedelta(days=30)
    purge_gap: timedelta = timedelta(days=1)  # Prevent lookahead

    # Anchored vs rolling
    anchored: bool = False  # False=rolling window, True=expanding

    # Statistical requirements
    min_trades_per_window: int = 30  # For statistical significance
    min_windows: int = 12            # Minimum walk-forward windows

    # Optimization
    objective_function: str = "sharpe"  # sharpe, sortino, calmar
    selection_method: str = "percentile_75"  # best, avg_top_n, percentile

    # Robustness checks
    parameter_stability_threshold: float = 0.3  # Max param variation
    wfe_target: float = 0.5  # Walk-forward efficiency target

    # Constraints
    max_drawdown_pct: float = 20.0
    min_profit_factor: float = 1.2
```

### Implementation

```python
import pandas as pd
from datetime import datetime, timedelta

class WalkForwardAnalyzer:
    """Walk-forward analysis for strategy validation."""

    def __init__(self, config: WalkForwardConfig):
        self.config = config
        self.results = []

    def run(
        self,
        strategy_class,
        param_grid: dict,
        data_start: datetime,
        data_end: datetime,
    ) -> dict:
        """Run walk-forward analysis."""

        windows = self._generate_windows(data_start, data_end)

        for i, (train_start, train_end, test_start, test_end) in enumerate(windows):
            self.log.info(f"Window {i+1}/{len(windows)}")

            # 1. Optimize on training period
            best_params = self._optimize(
                strategy_class,
                param_grid,
                train_start,
                train_end,
            )

            # 2. Test on out-of-sample period
            oos_result = self._backtest(
                strategy_class,
                best_params,
                test_start,
                test_end,
            )

            self.results.append({
                "window": i,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "best_params": best_params,
                "is_sharpe": self._get_is_sharpe(best_params),
                "oos_sharpe": oos_result["sharpe"],
                "oos_returns": oos_result["returns"],
                "oos_drawdown": oos_result["max_drawdown"],
                "trades": oos_result["trade_count"],
            })

        return self._compile_results()

    def _generate_windows(self, start: datetime, end: datetime) -> list:
        """Generate train/test windows."""
        windows = []
        current = start

        while True:
            train_start = current
            train_end = train_start + self.config.train_period

            # Add purge gap
            test_start = train_end + self.config.purge_gap
            test_end = test_start + self.config.test_period

            if test_end > end:
                break

            windows.append((train_start, train_end, test_start, test_end))

            # Move forward
            if self.config.anchored:
                # Anchored: expand training window
                current = start
                self.config.train_period += self.config.step_size
            else:
                # Rolling: slide window forward
                current += self.config.step_size

        return windows

    def _optimize(self, strategy_class, param_grid, start, end) -> dict:
        """Optimize parameters on training period."""
        best_params = None
        best_score = float('-inf')

        for params in self._param_combinations(param_grid):
            result = self._backtest(strategy_class, params, start, end)

            score = self._calculate_score(result)

            if score > best_score:
                best_score = score
                best_params = params

        return best_params

    def _calculate_score(self, result: dict) -> float:
        """Calculate optimization score."""
        if self.config.objective_function == "sharpe":
            return result["sharpe"]
        elif self.config.objective_function == "sortino":
            return result["sortino"]
        elif self.config.objective_function == "calmar":
            return result["calmar"]
        else:
            return result["sharpe"]

    def _compile_results(self) -> dict:
        """Compile walk-forward results."""
        df = pd.DataFrame(self.results)

        # Calculate walk-forward efficiency
        is_sharpes = df["is_sharpe"].values
        oos_sharpes = df["oos_sharpe"].values

        wfe = np.mean(oos_sharpes) / np.mean(is_sharpes) if np.mean(is_sharpes) > 0 else 0

        # Parameter stability
        param_stability = self._calculate_param_stability(df)

        return {
            "windows": len(self.results),
            "wfe": wfe,
            "wfe_passed": wfe >= self.config.wfe_target,
            "avg_oos_sharpe": np.mean(oos_sharpes),
            "std_oos_sharpe": np.std(oos_sharpes),
            "avg_is_sharpe": np.mean(is_sharpes),
            "param_stability": param_stability,
            "param_stability_passed": param_stability <= self.config.parameter_stability_threshold,
            "total_trades": df["trades"].sum(),
            "details": df.to_dict(orient="records"),
        }

    def _calculate_param_stability(self, df: pd.DataFrame) -> float:
        """Calculate parameter stability across windows."""
        # Coefficient of variation for each parameter
        params_df = pd.DataFrame(df["best_params"].tolist())

        cv_values = []
        for col in params_df.columns:
            if params_df[col].dtype in [int, float]:
                cv = params_df[col].std() / params_df[col].mean() if params_df[col].mean() != 0 else 0
                cv_values.append(cv)

        return np.mean(cv_values) if cv_values else 0
```

### Usage

```bash
# Run walk-forward via Makefile
make backtest-walkforward CONFIG=config/walkforward.yaml
```

```python
# Or programmatically
config = WalkForwardConfig(
    train_period=timedelta(days=90),
    test_period=timedelta(days=30),
    step_size=timedelta(days=30),
    min_windows=12,
)

analyzer = WalkForwardAnalyzer(config)
results = analyzer.run(
    strategy_class=EMACrossStrategy,
    param_grid={
        "fast_period": [5, 10, 15, 20],
        "slow_period": [20, 30, 40, 50],
    },
    data_start=datetime(2023, 1, 1),
    data_end=datetime(2024, 12, 31),
)

print(f"Walk-forward efficiency: {results['wfe']:.2f}")
print(f"Passed: {results['wfe_passed']}")
```

### Interpreting Results

| Metric | Good | Warning | Poor |
|--------|------|---------|------|
| **WFE** | > 0.5 | 0.3-0.5 | < 0.3 |
| **Param Stability** | < 0.3 | 0.3-0.5 | > 0.5 |
| **OOS Sharpe Std** | < 0.5 | 0.5-1.0 | > 1.0 |

**Walk-Forward Efficiency (WFE)**:
```
WFE = Average OOS Sharpe / Average IS Sharpe

WFE > 0.5  → Strategy generalizes well
WFE < 0.3  → Likely overfit
```

---

## Performance Metrics

### Standard Metrics

```python
from nautilus_trader.analysis.statistics import PortfolioStatistics

stats = PortfolioStatistics(returns)

metrics = {
    # Returns
    "total_return": stats.total_return(),
    "annual_return": stats.annual_return(),
    "monthly_return": stats.monthly_returns(),

    # Risk-adjusted
    "sharpe_ratio": stats.sharpe_ratio(),
    "sortino_ratio": stats.sortino_ratio(),
    "calmar_ratio": stats.calmar_ratio(),

    # Drawdown
    "max_drawdown": stats.max_drawdown(),
    "avg_drawdown": stats.avg_drawdown(),
    "max_drawdown_duration": stats.max_drawdown_duration(),

    # Win/loss
    "win_rate": stats.win_rate(),
    "profit_factor": stats.profit_factor(),
    "avg_win": stats.avg_win(),
    "avg_loss": stats.avg_loss(),

    # Activity
    "trade_count": stats.trade_count(),
    "avg_trade_duration": stats.avg_trade_duration(),
}
```

### Custom Metrics

```python
def calculate_metrics(returns: pd.Series, trades: pd.DataFrame) -> dict:
    """Calculate comprehensive performance metrics."""

    # Basic returns
    total_return = (1 + returns).prod() - 1
    annual_return = (1 + total_return) ** (252 / len(returns)) - 1

    # Risk metrics
    volatility = returns.std() * np.sqrt(252)
    downside_vol = returns[returns < 0].std() * np.sqrt(252)

    # Sharpe (assuming 0 risk-free rate for crypto)
    sharpe = annual_return / volatility if volatility > 0 else 0

    # Sortino
    sortino = annual_return / downside_vol if downside_vol > 0 else 0

    # Maximum drawdown
    cumulative = (1 + returns).cumprod()
    rolling_max = cumulative.expanding().max()
    drawdowns = cumulative / rolling_max - 1
    max_drawdown = drawdowns.min()

    # Calmar
    calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

    # Win rate
    winning_trades = trades[trades["pnl"] > 0]
    win_rate = len(winning_trades) / len(trades) if len(trades) > 0 else 0

    # Profit factor
    gross_profit = trades[trades["pnl"] > 0]["pnl"].sum()
    gross_loss = abs(trades[trades["pnl"] < 0]["pnl"].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "volatility": volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "calmar_ratio": calmar,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "trade_count": len(trades),
    }
```

---

## Parameter Optimization

### Grid Search

```python
from itertools import product

def grid_search(
    strategy_class,
    param_grid: dict,
    data,
    instrument,
    venue_config,
) -> pd.DataFrame:
    """Run grid search optimization."""

    results = []
    combinations = list(product(*param_grid.values()))
    param_names = list(param_grid.keys())

    for combo in combinations:
        params = dict(zip(param_names, combo))

        # Run backtest
        result = run_single_backtest(
            strategy_class,
            params,
            data,
            instrument,
            venue_config,
        )

        results.append({
            **params,
            "sharpe": result["sharpe"],
            "return": result["total_return"],
            "drawdown": result["max_drawdown"],
            "trades": result["trade_count"],
        })

    return pd.DataFrame(results).sort_values("sharpe", ascending=False)
```

### Bayesian Optimization

```python
from skopt import gp_minimize
from skopt.space import Integer, Real

def bayesian_optimize(
    strategy_class,
    param_space: list,
    data,
    n_calls: int = 50,
) -> dict:
    """Bayesian optimization for parameters."""

    def objective(params):
        result = run_single_backtest(strategy_class, params, data)
        return -result["sharpe"]  # Minimize negative Sharpe

    result = gp_minimize(
        objective,
        param_space,
        n_calls=n_calls,
        random_state=42,
    )

    return {
        "best_params": result.x,
        "best_sharpe": -result.fun,
        "convergence": result.func_vals,
    }

# Usage
param_space = [
    Integer(5, 30, name="fast_period"),
    Integer(20, 100, name="slow_period"),
    Real(0.001, 0.1, name="trade_size"),
]
```

---

## Generating Reports

### Performance Report

```bash
make backtest-report RESULTS=results/backtest_2024.json
```

```python
def generate_report(results: dict, output_path: str):
    """Generate HTML performance report."""

    html = f"""
    <html>
    <head><title>Backtest Report</title></head>
    <body>
    <h1>Backtest Report</h1>

    <h2>Summary</h2>
    <table>
        <tr><td>Total Return</td><td>{results['total_return']:.2%}</td></tr>
        <tr><td>Sharpe Ratio</td><td>{results['sharpe']:.2f}</td></tr>
        <tr><td>Max Drawdown</td><td>{results['max_drawdown']:.2%}</td></tr>
        <tr><td>Win Rate</td><td>{results['win_rate']:.1%}</td></tr>
        <tr><td>Trade Count</td><td>{results['trade_count']}</td></tr>
    </table>

    <h2>Equity Curve</h2>
    <img src="equity_curve.png" />

    <h2>Drawdown</h2>
    <img src="drawdown.png" />

    <h2>Monthly Returns</h2>
    {results['monthly_returns'].to_html()}

    </body>
    </html>
    """

    with open(output_path, "w") as f:
        f.write(html)
```

### Comparison Report

```bash
make backtest-compare RESULTS='results/run1.json results/run2.json'
```

```python
def compare_backtests(results_list: list[dict]) -> pd.DataFrame:
    """Compare multiple backtest results."""

    comparison = []
    for result in results_list:
        comparison.append({
            "name": result["name"],
            "sharpe": result["sharpe"],
            "return": result["total_return"],
            "drawdown": result["max_drawdown"],
            "win_rate": result["win_rate"],
            "trades": result["trade_count"],
        })

    df = pd.DataFrame(comparison)
    return df.sort_values("sharpe", ascending=False)
```

---

## Common Pitfalls

### 1. Lookahead Bias

```python
# ❌ WRONG: Using future data
def on_bar(self, bar: Bar):
    future_price = self.data[self.bar_index + 10]  # Lookahead!

# ✅ CORRECT: Only use past data
def on_bar(self, bar: Bar):
    self.indicator.update(bar.close)
    signal = self.indicator.value  # Uses only past data
```

### 2. Survivorship Bias

```python
# ❌ WRONG: Only testing on current top coins
instruments = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]  # Survivors

# ✅ CORRECT: Include delisted instruments
instruments = get_all_instruments_for_period(start, end)  # Includes failures
```

### 3. Overfitting

```python
# ❌ WRONG: Too many parameters, optimized on full dataset
config = StrategyConfig(
    param1=optimized_value_1,  # Optimized on 2020-2024
    param2=optimized_value_2,
    param3=optimized_value_3,
    # ... 20 more parameters
)

# ✅ CORRECT: Few parameters, walk-forward validated
config = StrategyConfig(
    fast_period=10,   # Walk-forward validated
    slow_period=20,   # Walk-forward validated
)
```

### 4. Unrealistic Fills

```python
# ❌ WRONG: Assuming perfect fills
fill_model = FillModel(
    prob_fill_on_limit=1.0,  # Always fills
    prob_slippage=0.0,       # No slippage
)

# ✅ CORRECT: Realistic fills
fill_model = FillModel(
    prob_fill_on_limit=0.8,
    prob_fill_on_stop=0.9,
    prob_slippage=0.5,
)
```

---

## Next Steps

1. **Validate statistically**: [QUANTITATIVE_VALIDATION.md](QUANTITATIVE_VALIDATION.md)
2. **Deploy carefully**: [DEPLOYMENT.md](DEPLOYMENT.md)
