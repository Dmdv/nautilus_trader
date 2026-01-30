"""
Walk-Forward Analysis Module.

Provides walk-forward optimization and out-of-sample validation
to detect overfitting and validate strategy robustness.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from .analysis import EquityAnalyzer, PerformanceMetrics


@dataclass
class WalkForwardConfig:
    """
    Configuration for walk-forward analysis.

    Attributes:
        train_period: Training window duration.
        test_period: Testing window duration.
        step_size: Step size between windows.
        purge_gap: Gap between train/test to prevent lookahead.
        min_trades_per_window: Minimum trades required per window.
        min_windows: Minimum number of walk-forward windows.
        objective_function: Metric to optimize ("sharpe", "return", "sortino").
        wfe_target: Walk-forward efficiency target (0.5 = good).
    """

    train_period: timedelta = field(default_factory=lambda: timedelta(days=90))
    test_period: timedelta = field(default_factory=lambda: timedelta(days=30))
    step_size: timedelta = field(default_factory=lambda: timedelta(days=30))
    purge_gap: timedelta = field(default_factory=lambda: timedelta(days=1))
    min_trades_per_window: int = 30
    min_windows: int = 12
    objective_function: str = "sharpe"
    wfe_target: float = 0.5


@dataclass
class WalkForwardWindow:
    """
    Single walk-forward window result.

    Attributes:
        window_id: Window identifier.
        train_start: Training period start.
        train_end: Training period end.
        test_start: Test period start.
        test_end: Test period end.
        train_metrics: Metrics from training period.
        test_metrics: Metrics from test period.
        optimal_params: Optimal parameters from training.
        trade_count: Number of trades in test period.
    """

    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_metrics: PerformanceMetrics
    test_metrics: PerformanceMetrics
    optimal_params: dict[str, Any] = field(default_factory=dict)
    trade_count: int = 0


@dataclass
class WalkForwardResult:
    """
    Complete walk-forward analysis result.

    Attributes:
        config: Configuration used.
        windows: List of individual window results.
        aggregate_metrics: Combined metrics across all test periods.
        wfe: Walk-forward efficiency.
        is_robust: Whether strategy passes robustness criteria.
        analysis_summary: Summary of findings.
    """

    config: WalkForwardConfig
    windows: list[WalkForwardWindow]
    aggregate_metrics: PerformanceMetrics
    wfe: float
    is_robust: bool
    analysis_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "wfe": self.wfe,
            "is_robust": self.is_robust,
            "num_windows": len(self.windows),
            "aggregate_metrics": self.aggregate_metrics.to_dict(),
            "analysis_summary": self.analysis_summary,
        }


class WalkForwardAnalyzer:
    """
    Walk-forward analysis for strategy validation.

    Implements anchored or rolling walk-forward analysis to test
    strategy out-of-sample performance and detect overfitting.

    Walk-Forward Efficiency (WFE):
        WFE = (Out-of-sample Sharpe) / (In-sample Sharpe)

    Interpretation:
        - WFE > 0.5: Good - strategy generalizes well
        - WFE 0.3-0.5: Warning - possible overfitting
        - WFE < 0.3: Poor - likely overfit
    """

    def __init__(self, config: WalkForwardConfig) -> None:
        """
        Initialize walk-forward analyzer.

        Args:
            config: Walk-forward configuration.
        """
        self.config = config
        self._windows: list[WalkForwardWindow] = []

    def generate_windows(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[tuple[datetime, datetime, datetime, datetime]]:
        """
        Generate train/test window boundaries.

        Args:
            start_date: Data start date.
            end_date: Data end date.

        Returns:
            List of (train_start, train_end, test_start, test_end) tuples.
        """
        windows = []
        current_train_start = start_date

        window_id = 0
        while True:
            train_end = current_train_start + self.config.train_period
            test_start = train_end + self.config.purge_gap
            test_end = test_start + self.config.test_period

            # Check if we have enough data
            if test_end > end_date:
                break

            windows.append((current_train_start, train_end, test_start, test_end))

            # Move to next window
            current_train_start += self.config.step_size
            window_id += 1

        return windows

    def run_window(
        self,
        window_id: int,
        train_start: datetime,
        train_end: datetime,
        test_start: datetime,
        test_end: datetime,
        train_equity: list[float],
        test_equity: list[float],
        optimal_params: dict[str, Any] | None = None,
        trade_count: int = 0,
    ) -> WalkForwardWindow:
        """
        Analyze a single walk-forward window.

        Args:
            window_id: Window identifier.
            train_start: Training period start.
            train_end: Training period end.
            test_start: Test period start.
            test_end: Test period end.
            train_equity: Equity curve during training.
            test_equity: Equity curve during testing.
            optimal_params: Parameters optimized during training.
            trade_count: Number of trades in test period.

        Returns:
            WalkForwardWindow with analysis results.
        """
        # Analyze training period
        train_analyzer = EquityAnalyzer(train_equity)
        train_metrics = train_analyzer.calculate_metrics()

        # Analyze test period
        test_analyzer = EquityAnalyzer(test_equity)
        test_metrics = test_analyzer.calculate_metrics()

        return WalkForwardWindow(
            window_id=window_id,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            train_metrics=train_metrics,
            test_metrics=test_metrics,
            optimal_params=optimal_params or {},
            trade_count=trade_count,
        )

    def calculate_wfe(self, windows: list[WalkForwardWindow]) -> float:
        """
        Calculate Walk-Forward Efficiency.

        WFE = avg(test Sharpe) / avg(train Sharpe)

        Args:
            windows: List of walk-forward windows.

        Returns:
            Walk-forward efficiency (0-1+).
        """
        if not windows:
            return 0.0

        train_sharpes = [w.train_metrics.sharpe_ratio for w in windows]
        test_sharpes = [w.test_metrics.sharpe_ratio for w in windows]

        avg_train_sharpe = np.mean(train_sharpes) if train_sharpes else 0.0
        avg_test_sharpe = np.mean(test_sharpes) if test_sharpes else 0.0

        if avg_train_sharpe <= 0:
            return 0.0

        return float(avg_test_sharpe / avg_train_sharpe)

    def aggregate_test_results(
        self,
        windows: list[WalkForwardWindow],
    ) -> PerformanceMetrics:
        """
        Aggregate test period results across all windows.

        Args:
            windows: List of walk-forward windows.

        Returns:
            Combined performance metrics.
        """
        if not windows:
            return PerformanceMetrics()

        # Collect test metrics
        total_returns = [w.test_metrics.total_return for w in windows]
        sharpes = [w.test_metrics.sharpe_ratio for w in windows]
        max_dds = [w.test_metrics.max_drawdown for w in windows]
        win_rates = [w.test_metrics.win_rate for w in windows]

        return PerformanceMetrics(
            total_return=float(np.sum(total_returns)),
            annual_return=float(np.mean([w.test_metrics.annual_return for w in windows])),
            sharpe_ratio=float(np.mean(sharpes)),
            max_drawdown=float(np.max(max_dds)),
            avg_drawdown=float(np.mean(max_dds)),
            win_rate=float(np.mean(win_rates)),
            trade_count=sum(w.trade_count for w in windows),
        )

    def analyze(
        self,
        windows: list[WalkForwardWindow],
    ) -> WalkForwardResult:
        """
        Complete walk-forward analysis.

        Args:
            windows: List of analyzed windows.

        Returns:
            Complete walk-forward result.
        """
        self._windows = windows

        # Calculate WFE
        wfe = self.calculate_wfe(windows)

        # Aggregate test results
        aggregate_metrics = self.aggregate_test_results(windows)

        # Determine robustness
        is_robust = self._check_robustness(windows, wfe)

        # Generate analysis summary
        summary = self._generate_summary(windows, wfe, is_robust)

        return WalkForwardResult(
            config=self.config,
            windows=windows,
            aggregate_metrics=aggregate_metrics,
            wfe=wfe,
            is_robust=is_robust,
            analysis_summary=summary,
        )

    def _check_robustness(
        self,
        windows: list[WalkForwardWindow],
        wfe: float,
    ) -> bool:
        """Check if strategy passes robustness criteria."""
        # Minimum windows
        if len(windows) < self.config.min_windows:
            return False

        # WFE threshold
        if wfe < self.config.wfe_target:
            return False

        # Check trade counts
        low_trade_windows = sum(
            1 for w in windows
            if w.trade_count < self.config.min_trades_per_window
        )
        if low_trade_windows > len(windows) * 0.2:  # More than 20% with low trades
            return False

        # Check for consistent positive test performance
        positive_windows = sum(
            1 for w in windows if w.test_metrics.total_return > 0
        )
        if positive_windows < len(windows) * 0.5:  # Less than 50% positive
            return False

        return True

    def _generate_summary(
        self,
        windows: list[WalkForwardWindow],
        wfe: float,
        is_robust: bool,
    ) -> dict[str, Any]:
        """Generate analysis summary."""
        train_sharpes = [w.train_metrics.sharpe_ratio for w in windows]
        test_sharpes = [w.test_metrics.sharpe_ratio for w in windows]

        # Sharpe decay analysis
        sharpe_decay = []
        for w in windows:
            if w.train_metrics.sharpe_ratio > 0:
                decay = 1 - (w.test_metrics.sharpe_ratio / w.train_metrics.sharpe_ratio)
                sharpe_decay.append(decay)

        summary = {
            "num_windows": len(windows),
            "wfe": wfe,
            "wfe_interpretation": self._interpret_wfe(wfe),
            "is_robust": is_robust,
            "avg_train_sharpe": float(np.mean(train_sharpes)) if train_sharpes else 0.0,
            "avg_test_sharpe": float(np.mean(test_sharpes)) if test_sharpes else 0.0,
            "train_sharpe_std": float(np.std(train_sharpes)) if len(train_sharpes) > 1 else 0.0,
            "test_sharpe_std": float(np.std(test_sharpes)) if len(test_sharpes) > 1 else 0.0,
            "avg_sharpe_decay": float(np.mean(sharpe_decay)) if sharpe_decay else 0.0,
            "positive_test_windows": sum(1 for w in windows if w.test_metrics.total_return > 0),
            "total_test_trades": sum(w.trade_count for w in windows),
        }

        # Add warnings
        warnings = []
        if wfe < 0.3:
            warnings.append("WFE < 0.3: High risk of overfitting")
        elif wfe < 0.5:
            warnings.append("WFE < 0.5: Moderate risk of overfitting")

        if summary["avg_sharpe_decay"] > 0.5:
            warnings.append("High Sharpe decay from train to test periods")

        if len(windows) < 12:
            warnings.append(f"Only {len(windows)} windows - may not be statistically reliable")

        summary["warnings"] = warnings

        return summary

    def _interpret_wfe(self, wfe: float) -> str:
        """Interpret WFE value."""
        if wfe >= 0.7:
            return "Excellent - strategy generalizes very well"
        elif wfe >= 0.5:
            return "Good - strategy generalizes well"
        elif wfe >= 0.3:
            return "Warning - possible overfitting, proceed with caution"
        else:
            return "Poor - likely overfit, not recommended for live trading"


def run_walk_forward_analysis(
    equity_by_date: dict[datetime, float],
    config: WalkForwardConfig | None = None,
    trade_counts: dict[tuple[datetime, datetime], int] | None = None,
) -> WalkForwardResult:
    """
    Convenience function to run walk-forward analysis on equity curve.

    Args:
        equity_by_date: Dictionary of date -> equity value.
        config: Walk-forward configuration (uses defaults if None).
        trade_counts: Optional trade counts per window period.

    Returns:
        WalkForwardResult with analysis.
    """
    config = config or WalkForwardConfig()
    analyzer = WalkForwardAnalyzer(config)

    # Get date range
    dates = sorted(equity_by_date.keys())
    if len(dates) < 2:
        return WalkForwardResult(
            config=config,
            windows=[],
            aggregate_metrics=PerformanceMetrics(),
            wfe=0.0,
            is_robust=False,
            analysis_summary={"error": "Insufficient data"},
        )

    start_date = dates[0]
    end_date = dates[-1]

    # Generate windows
    window_bounds = analyzer.generate_windows(start_date, end_date)

    if not window_bounds:
        return WalkForwardResult(
            config=config,
            windows=[],
            aggregate_metrics=PerformanceMetrics(),
            wfe=0.0,
            is_robust=False,
            analysis_summary={"error": "Insufficient data for walk-forward windows"},
        )

    # Analyze each window
    windows = []
    for i, (train_start, train_end, test_start, test_end) in enumerate(window_bounds):
        # Extract equity for each period
        train_equity = [
            equity_by_date[d] for d in dates
            if train_start <= d <= train_end
        ]
        test_equity = [
            equity_by_date[d] for d in dates
            if test_start <= d <= test_end
        ]

        if len(train_equity) < 10 or len(test_equity) < 5:
            continue

        # Get trade count if available
        trade_count = 0
        if trade_counts:
            trade_count = trade_counts.get((test_start, test_end), 0)

        window = analyzer.run_window(
            window_id=i,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            train_equity=train_equity,
            test_equity=test_equity,
            trade_count=trade_count,
        )
        windows.append(window)

    return analyzer.analyze(windows)
