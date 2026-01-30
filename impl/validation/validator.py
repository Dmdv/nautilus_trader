"""
Strategy Validation Pipeline.

Provides a comprehensive validation framework combining all
statistical tests for strategy robustness assessment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

from ..backtesting.analysis import (
    PerformanceMetrics,
    EquityAnalyzer,
    MonteCarloResult,
    BootstrapResult,
    monte_carlo_permutation_test,
    bootstrap_confidence_interval,
    calculate_deflated_sharpe_ratio,
)
from ..backtesting.walkforward import (
    WalkForwardResult,
    run_walk_forward_analysis,
)
from .stationarity import StationarityTestSuite, run_stationarity_tests
from .regime import (
    SimpleRegimeDetector,
    analyze_regime_performance,
)


@dataclass
class ValidationConfig:
    """
    Configuration for strategy validation.

    Attributes:
        min_sharpe: Minimum acceptable Sharpe ratio.
        min_trades: Minimum number of trades.
        max_drawdown: Maximum acceptable drawdown.
        min_wfe: Minimum walk-forward efficiency.
        monte_carlo_permutations: Number of MC permutations.
        bootstrap_samples: Number of bootstrap samples.
        significance_level: Statistical significance level.
        max_half_life: Maximum acceptable half-life for stat arb.
        n_trials_for_dsr: Number of strategies tested (for DSR).
    """

    min_sharpe: float = 0.5
    min_trades: int = 100
    max_drawdown: float = 0.20
    min_wfe: float = 0.5
    monte_carlo_permutations: int = 1000
    bootstrap_samples: int = 1000
    significance_level: float = 0.05
    max_half_life: float = 30.0
    n_trials_for_dsr: int = 10


@dataclass
class ValidationResult:
    """
    Complete validation result.

    Attributes:
        passed: Whether strategy passes all validation criteria.
        overall_score: Overall validation score (0-1).
        performance_metrics: Basic performance metrics.
        monte_carlo: Monte Carlo test result.
        bootstrap_sharpe: Bootstrap CI for Sharpe ratio.
        deflated_sharpe: Deflated Sharpe Ratio.
        walk_forward: Walk-forward analysis result.
        regime_analysis: Regime detection and conditional performance.
        stationarity: Stationarity tests (for stat arb strategies).
        warnings: List of warnings.
        failures: List of failed criteria.
        timestamp: Validation timestamp.
    """

    passed: bool
    overall_score: float
    performance_metrics: PerformanceMetrics
    monte_carlo: MonteCarloResult | None
    bootstrap_sharpe: BootstrapResult | None
    deflated_sharpe: float
    walk_forward: WalkForwardResult | None
    regime_analysis: dict[str, Any] | None
    stationarity: StationarityTestSuite | None
    warnings: list[str]
    failures: list[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "passed": self.passed,
            "overall_score": self.overall_score,
            "performance_metrics": self.performance_metrics.to_dict(),
            "monte_carlo": {
                "p_value": self.monte_carlo.p_value,
                "is_significant": self.monte_carlo.is_significant,
            } if self.monte_carlo else None,
            "bootstrap_sharpe": {
                "ci_lower": self.bootstrap_sharpe.ci_lower,
                "ci_upper": self.bootstrap_sharpe.ci_upper,
            } if self.bootstrap_sharpe else None,
            "deflated_sharpe": self.deflated_sharpe,
            "walk_forward": self.walk_forward.to_dict() if self.walk_forward else None,
            "stationarity": self.stationarity.to_dict() if self.stationarity else None,
            "warnings": self.warnings,
            "failures": self.failures,
            "timestamp": self.timestamp.isoformat(),
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"Strategy Validation: {status}",
            f"Overall Score: {self.overall_score:.2f}",
            "=" * 50,
            "",
            "Performance Metrics:",
            f"  Sharpe Ratio: {self.performance_metrics.sharpe_ratio:.2f}",
            f"  Total Return: {self.performance_metrics.total_return:.2%}",
            f"  Max Drawdown: {self.performance_metrics.max_drawdown:.2%}",
            f"  Trade Count: {self.performance_metrics.trade_count}",
            "",
        ]

        if self.monte_carlo:
            lines.extend([
                "Monte Carlo Test:",
                f"  P-value: {self.monte_carlo.p_value:.4f}",
                f"  Significant: {'Yes' if self.monte_carlo.is_significant else 'No'}",
                "",
            ])

        if self.bootstrap_sharpe:
            lines.extend([
                "Bootstrap Sharpe CI:",
                f"  95% CI: [{self.bootstrap_sharpe.ci_lower:.2f}, {self.bootstrap_sharpe.ci_upper:.2f}]",
                "",
            ])

        lines.append(f"Deflated Sharpe Ratio: {self.deflated_sharpe:.3f}")

        if self.walk_forward:
            lines.extend([
                "",
                "Walk-Forward Analysis:",
                f"  WFE: {self.walk_forward.wfe:.2f}",
                f"  Robust: {'Yes' if self.walk_forward.is_robust else 'No'}",
            ])

        if self.warnings:
            lines.extend(["", "Warnings:"] + [f"  - {w}" for w in self.warnings])

        if self.failures:
            lines.extend(["", "Failures:"] + [f"  - {f}" for f in self.failures])

        return "\n".join(lines)


class StrategyValidator:
    """
    Comprehensive strategy validator.

    Runs all validation tests and provides overall assessment.
    """

    def __init__(self, config: ValidationConfig | None = None) -> None:
        """
        Initialize validator.

        Args:
            config: Validation configuration.
        """
        self.config = config or ValidationConfig()

    def validate(
        self,
        equity_curve: list[float],
        returns: list[float] | None = None,
        timestamps: list[datetime] | None = None,
        trades: list[dict[str, Any]] | None = None,
        spread_series: list[float] | None = None,
        is_stat_arb: bool = False,
    ) -> ValidationResult:
        """
        Run complete validation on strategy.

        Args:
            equity_curve: Equity curve values.
            returns: Return series (calculated from equity if None).
            timestamps: Timestamps for each equity value.
            trades: List of trade dictionaries.
            spread_series: Spread series for stat arb strategies.
            is_stat_arb: Whether this is a statistical arbitrage strategy.

        Returns:
            ValidationResult with all test results.
        """
        equity = np.array(equity_curve)
        warnings: list[str] = []
        failures: list[str] = []

        # Calculate returns if not provided
        if returns is None:
            returns_array = np.diff(equity) / equity[:-1]
        else:
            returns_array = np.array(returns)

        # Basic performance metrics
        analyzer = EquityAnalyzer(list(equity))
        performance = analyzer.calculate_metrics()

        # Check basic criteria
        if performance.sharpe_ratio < self.config.min_sharpe:
            failures.append(
                f"Sharpe ratio {performance.sharpe_ratio:.2f} below minimum {self.config.min_sharpe}"
            )

        if performance.max_drawdown > self.config.max_drawdown:
            failures.append(
                f"Max drawdown {performance.max_drawdown:.2%} exceeds limit {self.config.max_drawdown:.2%}"
            )

        if performance.trade_count < self.config.min_trades:
            warnings.append(
                f"Trade count {performance.trade_count} below recommended {self.config.min_trades}"
            )

        # Monte Carlo test
        monte_carlo = None
        if len(returns_array) >= 30:
            monte_carlo = monte_carlo_permutation_test(
                returns_array,
                n_permutations=self.config.monte_carlo_permutations,
            )

            if not monte_carlo.is_significant:
                failures.append(
                    f"Monte Carlo test failed (p-value: {monte_carlo.p_value:.4f})"
                )

        # Bootstrap confidence interval for Sharpe
        bootstrap_sharpe = None
        if len(returns_array) >= 30:
            def sharpe_func(rets: np.ndarray) -> float:
                std = np.std(rets)
                if std < 1e-10:
                    return 0.0
                return float(np.mean(rets) / std * np.sqrt(252))

            bootstrap_sharpe = bootstrap_confidence_interval(
                returns_array,
                metric_func=sharpe_func,
                n_bootstrap=self.config.bootstrap_samples,
                metric_name="sharpe_ratio",
            )

            if bootstrap_sharpe.ci_lower < 0:
                warnings.append(
                    f"Sharpe ratio 95% CI includes zero [{bootstrap_sharpe.ci_lower:.2f}, {bootstrap_sharpe.ci_upper:.2f}]"
                )

        # Deflated Sharpe Ratio
        deflated_sharpe = calculate_deflated_sharpe_ratio(
            sharpe=performance.sharpe_ratio,
            n_trials=self.config.n_trials_for_dsr,
            n_observations=len(returns_array),
        )

        if deflated_sharpe < 0.5:
            warnings.append(
                f"Deflated Sharpe Ratio {deflated_sharpe:.3f} suggests possible data snooping"
            )

        # Walk-forward analysis
        walk_forward = None
        if timestamps and len(equity) > 100:
            equity_by_date = {t: e for t, e in zip(timestamps, equity)}
            walk_forward = run_walk_forward_analysis(equity_by_date)

            if walk_forward.wfe < self.config.min_wfe:
                failures.append(
                    f"Walk-forward efficiency {walk_forward.wfe:.2f} below minimum {self.config.min_wfe}"
                )

        # Regime analysis
        regime_analysis = None
        if len(returns_array) >= 50:
            detector = SimpleRegimeDetector()
            regime_result = detector.detect_regimes(list(returns_array))

            regime_perf = analyze_regime_performance(
                returns_array,
                regime_result.regime_sequence,
                trades=trades,
            )

            regime_analysis = {
                "current_regime": regime_result.current_regime,
                "regime_stats": regime_result.regime_stats,
                "regime_performance": {k: v.to_dict() for k, v in regime_perf.items()},
            }

            # Check for regime-dependent performance issues
            for regime, perf in regime_perf.items():
                if perf.sharpe_ratio < -0.5:
                    warnings.append(
                        f"Negative Sharpe ({perf.sharpe_ratio:.2f}) in {regime} regime"
                    )

        # Stationarity tests (for stat arb)
        stationarity = None
        if is_stat_arb and spread_series is not None:
            stationarity = run_stationarity_tests(
                spread_series,
                max_acceptable_half_life=self.config.max_half_life,
            )

            if not stationarity.overall_stationary:
                failures.append("Spread is not stationary - stat arb may not be viable")

        # Calculate overall score
        overall_score = self._calculate_overall_score(
            performance,
            monte_carlo,
            bootstrap_sharpe,
            deflated_sharpe,
            walk_forward,
            stationarity,
        )

        # Determine pass/fail
        passed = len(failures) == 0

        return ValidationResult(
            passed=passed,
            overall_score=overall_score,
            performance_metrics=performance,
            monte_carlo=monte_carlo,
            bootstrap_sharpe=bootstrap_sharpe,
            deflated_sharpe=deflated_sharpe,
            walk_forward=walk_forward,
            regime_analysis=regime_analysis,
            stationarity=stationarity,
            warnings=warnings,
            failures=failures,
        )

    def _calculate_overall_score(
        self,
        performance: PerformanceMetrics,
        monte_carlo: MonteCarloResult | None,
        bootstrap_sharpe: BootstrapResult | None,
        deflated_sharpe: float,
        walk_forward: WalkForwardResult | None,
        stationarity: StationarityTestSuite | None,
    ) -> float:
        """Calculate overall validation score (0-1)."""
        scores: list[float] = []
        weights: list[float] = []

        # Sharpe ratio score (capped at 3)
        sharpe_score = min(performance.sharpe_ratio / 3.0, 1.0)
        scores.append(max(0.0, sharpe_score))
        weights.append(0.2)

        # Drawdown score
        dd_score = 1.0 - min(performance.max_drawdown / 0.3, 1.0)
        scores.append(max(0.0, dd_score))
        weights.append(0.15)

        # Monte Carlo score
        if monte_carlo:
            mc_score = 1.0 if monte_carlo.is_significant else 0.0
            scores.append(mc_score)
            weights.append(0.2)

        # Bootstrap CI score
        if bootstrap_sharpe:
            ci_score = 1.0 if bootstrap_sharpe.ci_lower > 0 else 0.5
            scores.append(ci_score)
            weights.append(0.1)

        # DSR score
        dsr_score = min(deflated_sharpe * 2, 1.0)
        scores.append(max(0.0, dsr_score))
        weights.append(0.15)

        # Walk-forward score
        if walk_forward:
            wfe_score = min(walk_forward.wfe / 0.7, 1.0)
            scores.append(max(0.0, wfe_score))
            weights.append(0.2)

        # Stationarity score (for stat arb strategies)
        if stationarity:
            stat_score = 1.0 if stationarity.overall_stationary else 0.0
            scores.append(stat_score)
            weights.append(0.15)

        # Calculate weighted average
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0

        return sum(s * w for s, w in zip(scores, weights)) / total_weight


def validate_strategy(
    equity_curve: list[float],
    returns: list[float] | None = None,
    timestamps: list[datetime] | None = None,
    trades: list[dict[str, Any]] | None = None,
    config: ValidationConfig | None = None,
) -> ValidationResult:
    """
    Convenience function to validate a strategy.

    Args:
        equity_curve: Equity curve values.
        returns: Return series (optional).
        timestamps: Timestamps (optional).
        trades: Trade list (optional).
        config: Validation configuration.

    Returns:
        ValidationResult with complete analysis.
    """
    validator = StrategyValidator(config)
    return validator.validate(
        equity_curve=equity_curve,
        returns=returns,
        timestamps=timestamps,
        trades=trades,
    )
