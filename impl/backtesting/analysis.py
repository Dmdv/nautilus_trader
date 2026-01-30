"""
Backtest Analysis Module.

Provides analysis utilities for backtest results including
performance metrics, statistical tests, and report generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable

import numpy as np


@dataclass
class PerformanceMetrics:
    """
    Comprehensive performance metrics.

    Attributes:
        total_return: Total return over period.
        annual_return: Annualized return.
        monthly_return: Average monthly return.
        sharpe_ratio: Risk-adjusted return (Sharpe).
        sortino_ratio: Downside risk-adjusted return.
        calmar_ratio: Return / max drawdown.
        max_drawdown: Maximum drawdown.
        avg_drawdown: Average drawdown.
        max_drawdown_duration_days: Longest drawdown duration.
        volatility: Annualized volatility.
        downside_volatility: Annualized downside volatility.
        win_rate: Percentage of winning trades.
        profit_factor: Gross profit / gross loss.
        avg_win: Average winning trade.
        avg_loss: Average losing trade.
        trade_count: Total number of trades.
        avg_trade_duration_hours: Average trade holding period.
        expectancy: Expected value per trade.
    """

    total_return: float = 0.0
    annual_return: float = 0.0
    monthly_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    avg_drawdown: float = 0.0
    max_drawdown_duration_days: float = 0.0
    volatility: float = 0.0
    downside_volatility: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    trade_count: int = 0
    avg_trade_duration_hours: float = 0.0
    expectancy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "monthly_return": self.monthly_return,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "avg_drawdown": self.avg_drawdown,
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "volatility": self.volatility,
            "downside_volatility": self.downside_volatility,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "trade_count": self.trade_count,
            "avg_trade_duration_hours": self.avg_trade_duration_hours,
            "expectancy": self.expectancy,
        }


class EquityAnalyzer:
    """
    Analyze equity curve for performance metrics.

    Calculates returns, drawdowns, risk metrics from
    a time series of equity values.
    """

    def __init__(
        self,
        equity_curve: list[float],
        timestamps: list[datetime] | None = None,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> None:
        """
        Initialize equity analyzer.

        Args:
            equity_curve: List of equity values.
            timestamps: Optional timestamps for each value.
            risk_free_rate: Annual risk-free rate for Sharpe calculation.
            periods_per_year: Trading periods per year (252 for daily).
        """
        self.equity_curve = np.array(equity_curve)
        self.timestamps = timestamps
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year

        # Calculate returns
        self._returns = np.diff(self.equity_curve) / self.equity_curve[:-1]

    @property
    def returns(self) -> np.ndarray:
        """Get period returns."""
        return self._returns

    def calculate_metrics(self) -> PerformanceMetrics:
        """
        Calculate all performance metrics.

        Returns:
            PerformanceMetrics with calculated values.
        """
        metrics = PerformanceMetrics()

        if len(self.equity_curve) < 2:
            return metrics

        # Total return
        metrics.total_return = (
            self.equity_curve[-1] / self.equity_curve[0] - 1
        )

        # Annualized return
        n_periods = len(self._returns)
        if n_periods > 0:
            compound_return = (1 + metrics.total_return)
            years = n_periods / self.periods_per_year
            if years > 0:
                metrics.annual_return = compound_return ** (1 / years) - 1

        # Monthly return (approximate)
        metrics.monthly_return = metrics.annual_return / 12

        # Volatility
        if len(self._returns) > 1:
            metrics.volatility = float(np.std(self._returns) * np.sqrt(self.periods_per_year))

            # Downside volatility (only negative returns)
            downside_returns = self._returns[self._returns < 0]
            if len(downside_returns) > 0:
                metrics.downside_volatility = float(
                    np.std(downside_returns) * np.sqrt(self.periods_per_year)
                )

        # Sharpe ratio
        if metrics.volatility > 0:
            excess_return = metrics.annual_return - self.risk_free_rate
            metrics.sharpe_ratio = excess_return / metrics.volatility

        # Sortino ratio
        if metrics.downside_volatility > 0:
            excess_return = metrics.annual_return - self.risk_free_rate
            metrics.sortino_ratio = excess_return / metrics.downside_volatility

        # Drawdown analysis
        dd_metrics = self._calculate_drawdowns()
        metrics.max_drawdown = dd_metrics["max_drawdown"]
        metrics.avg_drawdown = dd_metrics["avg_drawdown"]
        metrics.max_drawdown_duration_days = dd_metrics["max_duration_days"]

        # Calmar ratio
        if metrics.max_drawdown > 0:
            metrics.calmar_ratio = metrics.annual_return / metrics.max_drawdown

        return metrics

    def _calculate_drawdowns(self) -> dict[str, float]:
        """Calculate drawdown metrics."""
        # Running maximum
        running_max = np.maximum.accumulate(self.equity_curve)

        # Drawdown at each point
        drawdowns = (running_max - self.equity_curve) / running_max

        max_drawdown = float(np.max(drawdowns))
        avg_drawdown = float(np.mean(drawdowns[drawdowns > 0])) if np.any(drawdowns > 0) else 0.0

        # Max drawdown duration
        max_duration = 0
        current_duration = 0
        for dd in drawdowns:
            if dd > 0:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        # Convert periods to days
        max_duration_days = max_duration * (365 / self.periods_per_year)

        return {
            "max_drawdown": max_drawdown,
            "avg_drawdown": avg_drawdown,
            "max_duration_days": max_duration_days,
            "drawdown_series": drawdowns,
        }


class TradeAnalyzer:
    """
    Analyze individual trades for performance metrics.
    """

    def __init__(self, trades: list[dict[str, Any]]) -> None:
        """
        Initialize trade analyzer.

        Args:
            trades: List of trade dictionaries with pnl, entry_time, exit_time.
        """
        self.trades = trades

    def calculate_metrics(self) -> dict[str, Any]:
        """
        Calculate trade-based metrics.

        Returns:
            Dictionary with trade metrics.
        """
        if not self.trades:
            return {
                "trade_count": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "expectancy": 0.0,
                "avg_duration_hours": 0.0,
            }

        pnls = [t.get("pnl", 0.0) for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        trade_count = len(pnls)
        win_rate = len(wins) / trade_count if trade_count > 0 else 0.0

        # Profit factor
        gross_profit = sum(wins) if wins else 0.0
        gross_loss = abs(sum(losses)) if losses else 0.0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0

        # Averages
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = sum(losses) / len(losses) if losses else 0.0

        # Expectancy
        expectancy = sum(pnls) / trade_count if trade_count > 0 else 0.0

        # Average duration
        durations = []
        for t in self.trades:
            if "entry_time" in t and "exit_time" in t:
                entry = t["entry_time"]
                exit_t = t["exit_time"]
                if isinstance(entry, datetime) and isinstance(exit_t, datetime):
                    duration = (exit_t - entry).total_seconds() / 3600
                    durations.append(duration)

        avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "trade_count": trade_count,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "expectancy": expectancy,
            "avg_duration_hours": avg_duration,
        }


@dataclass
class MonteCarloResult:
    """
    Results from Monte Carlo simulation.

    Attributes:
        original_sharpe: Original strategy Sharpe ratio.
        permuted_sharpes: Sharpe ratios from permutations.
        p_value: Statistical p-value.
        percentile_95: 95th percentile of permuted Sharpes.
        is_significant: Whether strategy is statistically significant.
    """

    original_sharpe: float
    permuted_sharpes: list[float]
    p_value: float
    percentile_95: float
    is_significant: bool


def monte_carlo_permutation_test(
    returns: list[float] | np.ndarray,
    n_permutations: int = 1000,
    confidence_level: float = 0.95,
) -> MonteCarloResult:
    """
    Run Monte Carlo permutation test for strategy significance.

    Tests whether strategy returns are significantly better than random
    by comparing to permuted (randomized) returns.

    Args:
        returns: Strategy returns.
        n_permutations: Number of permutations to run.
        confidence_level: Confidence level for significance.

    Returns:
        MonteCarloResult with p-value and significance.
    """
    returns = np.array(returns)

    # Calculate original Sharpe
    if len(returns) < 2 or np.std(returns) < 1e-10:
        return MonteCarloResult(
            original_sharpe=0.0,
            permuted_sharpes=[],
            p_value=1.0,
            percentile_95=0.0,
            is_significant=False,
        )

    original_sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)

    # Generate permuted Sharpe ratios
    permuted_sharpes = []
    rng = np.random.default_rng(42)

    for _ in range(n_permutations):
        # Shuffle returns (destroys any alpha)
        permuted = rng.permutation(returns)
        std = np.std(permuted)
        if std > 1e-10:
            perm_sharpe = np.mean(permuted) / std * np.sqrt(252)
            permuted_sharpes.append(float(perm_sharpe))

    if not permuted_sharpes:
        return MonteCarloResult(
            original_sharpe=float(original_sharpe),
            permuted_sharpes=[],
            p_value=1.0,
            percentile_95=0.0,
            is_significant=False,
        )

    # Calculate p-value (how many permutations beat original)
    permuted_array = np.array(permuted_sharpes)
    p_value = float(np.mean(permuted_array >= original_sharpe))

    # Get confidence percentile
    percentile_95 = float(np.percentile(permuted_array, confidence_level * 100))

    # Significance test
    is_significant = original_sharpe > percentile_95

    return MonteCarloResult(
        original_sharpe=float(original_sharpe),
        permuted_sharpes=permuted_sharpes,
        p_value=p_value,
        percentile_95=percentile_95,
        is_significant=is_significant,
    )


@dataclass
class BootstrapResult:
    """
    Results from bootstrap analysis.

    Attributes:
        metric_name: Name of the metric bootstrapped.
        original_value: Original metric value.
        mean: Bootstrap mean.
        std: Bootstrap standard deviation.
        ci_lower: Lower confidence interval bound.
        ci_upper: Upper confidence interval bound.
        confidence_level: Confidence level used.
    """

    metric_name: str
    original_value: float
    mean: float
    std: float
    ci_lower: float
    ci_upper: float
    confidence_level: float = 0.95


def bootstrap_confidence_interval(
    returns: list[float] | np.ndarray,
    metric_func: Callable[[np.ndarray], float],
    n_bootstrap: int = 1000,
    confidence_level: float = 0.95,
    metric_name: str = "metric",
) -> BootstrapResult:
    """
    Calculate bootstrap confidence interval for a metric.

    Args:
        returns: Return series.
        metric_func: Function to calculate metric from returns.
        n_bootstrap: Number of bootstrap samples.
        confidence_level: Confidence level for interval.
        metric_name: Name of the metric for reporting.

    Returns:
        BootstrapResult with confidence intervals.
    """
    returns = np.array(returns)
    n = len(returns)

    if n < 10:
        original = float(metric_func(returns))
        return BootstrapResult(
            metric_name=metric_name,
            original_value=original,
            mean=original,
            std=0.0,
            ci_lower=original,
            ci_upper=original,
            confidence_level=confidence_level,
        )

    # Original metric
    original = float(metric_func(returns))

    # Bootstrap samples
    rng = np.random.default_rng(42)
    bootstrap_metrics = []

    for _ in range(n_bootstrap):
        # Resample with replacement
        sample = rng.choice(returns, size=n, replace=True)
        bootstrap_metrics.append(float(metric_func(sample)))

    bootstrap_array = np.array(bootstrap_metrics)

    # Calculate statistics
    alpha = 1 - confidence_level
    ci_lower = float(np.percentile(bootstrap_array, alpha / 2 * 100))
    ci_upper = float(np.percentile(bootstrap_array, (1 - alpha / 2) * 100))

    return BootstrapResult(
        metric_name=metric_name,
        original_value=original,
        mean=float(np.mean(bootstrap_array)),
        std=float(np.std(bootstrap_array)),
        ci_lower=ci_lower,
        ci_upper=ci_upper,
        confidence_level=confidence_level,
    )


def calculate_deflated_sharpe_ratio(
    sharpe: float,
    n_trials: int,
    n_observations: int,
    returns_skewness: float = 0.0,
    returns_kurtosis: float = 3.0,
) -> float:
    """
    Calculate Deflated Sharpe Ratio accounting for multiple testing.

    DSR adjusts Sharpe ratio for data mining bias when many strategies
    are tested and only the best is reported.

    Args:
        sharpe: Observed Sharpe ratio.
        n_trials: Number of strategies/parameters tested.
        n_observations: Number of return observations.
        returns_skewness: Skewness of returns.
        returns_kurtosis: Kurtosis of returns.

    Returns:
        Deflated Sharpe Ratio (probability strategy is skillful).
    """
    from scipy import stats

    if n_trials <= 0 or n_observations <= 0:
        return 0.0

    # Expected maximum Sharpe under null hypothesis
    # Using Bailey-Lopez de Prado formula
    euler = 0.5772156649  # Euler-Mascheroni constant

    # Expected max Sharpe from trying n_trials random strategies
    e_max_sharpe = (1 - euler) * stats.norm.ppf(1 - 1 / n_trials) + \
                   euler * stats.norm.ppf(1 - 1 / (n_trials * np.e))

    # Variance of Sharpe estimator
    sharpe_var = (1 + 0.5 * sharpe**2 - returns_skewness * sharpe +
                  (returns_kurtosis - 3) / 4 * sharpe**2) / (n_observations - 1)

    if sharpe_var <= 0:
        return 0.0

    sharpe_std = np.sqrt(sharpe_var)

    # Deflated Sharpe: P(true Sharpe > 0)
    dsr = stats.norm.cdf((sharpe - e_max_sharpe) / sharpe_std)

    return float(dsr)
