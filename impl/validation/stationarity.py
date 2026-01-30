"""
Stationarity Tests Module.

Provides statistical tests for time series stationarity,
essential for validating mean-reversion strategies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class ADFResult:
    """
    Augmented Dickey-Fuller test result.

    Attributes:
        adf_statistic: ADF test statistic.
        p_value: P-value for the test.
        used_lag: Number of lags used.
        n_obs: Number of observations.
        critical_values: Critical values at 1%, 5%, 10%.
        is_stationary: Whether series is stationary at 5% level.
    """

    adf_statistic: float
    p_value: float
    used_lag: int
    n_obs: int
    critical_values: dict[str, float]
    is_stationary: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "adf_statistic": self.adf_statistic,
            "p_value": self.p_value,
            "used_lag": self.used_lag,
            "n_obs": self.n_obs,
            "critical_values": self.critical_values,
            "is_stationary": self.is_stationary,
        }


@dataclass
class HurstResult:
    """
    Hurst exponent estimation result.

    Attributes:
        hurst_exponent: Estimated Hurst exponent.
        interpretation: String interpretation of value.
        is_mean_reverting: True if H < 0.5.
        is_trending: True if H > 0.5.
        is_random_walk: True if H ≈ 0.5.
        confidence_interval: Optional CI bounds.
    """

    hurst_exponent: float
    interpretation: str
    is_mean_reverting: bool
    is_trending: bool
    is_random_walk: bool
    confidence_interval: tuple[float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hurst_exponent": self.hurst_exponent,
            "interpretation": self.interpretation,
            "is_mean_reverting": self.is_mean_reverting,
            "is_trending": self.is_trending,
            "is_random_walk": self.is_random_walk,
            "confidence_interval": self.confidence_interval,
        }


@dataclass
class HalfLifeResult:
    """
    Half-life estimation result.

    Attributes:
        half_life: Estimated half-life in periods.
        theta: Mean-reversion speed parameter.
        mu: Long-term mean estimate.
        is_valid: Whether estimation is valid.
        interpretation: Human-readable interpretation.
    """

    half_life: float
    theta: float
    mu: float
    is_valid: bool
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "half_life": self.half_life,
            "theta": self.theta,
            "mu": self.mu,
            "is_valid": self.is_valid,
            "interpretation": self.interpretation,
        }


def adf_test(
    series: list[float] | np.ndarray,
    max_lag: int | None = None,
    regression: str = "c",
) -> ADFResult:
    """
    Perform Augmented Dickey-Fuller test for stationarity.

    Tests null hypothesis that series has unit root (non-stationary).
    Rejection (low p-value) indicates stationarity.

    Args:
        series: Time series data.
        max_lag: Maximum lag for autoregression (auto-selected if None).
        regression: Regression type ('c' for constant, 'ct' for constant+trend).

    Returns:
        ADFResult with test statistics.
    """
    series = np.array(series)

    if len(series) < 20:
        return ADFResult(
            adf_statistic=0.0,
            p_value=1.0,
            used_lag=0,
            n_obs=len(series),
            critical_values={"1%": -3.43, "5%": -2.86, "10%": -2.57},
            is_stationary=False,
        )

    try:
        from statsmodels.tsa.stattools import adfuller

        result = adfuller(series, maxlag=max_lag, regression=regression)

        adf_stat = float(result[0])
        p_value = float(result[1])
        used_lag = int(result[2])
        n_obs = int(result[3])
        crit_values = {k: float(v) for k, v in result[4].items()}

        return ADFResult(
            adf_statistic=adf_stat,
            p_value=p_value,
            used_lag=used_lag,
            n_obs=n_obs,
            critical_values=crit_values,
            is_stationary=p_value < 0.05,
        )

    except ImportError:
        # Fallback without statsmodels - simple variance ratio test
        return _simple_stationarity_test(series)


def _simple_stationarity_test(series: np.ndarray) -> ADFResult:
    """
    Simple stationarity test without statsmodels.

    Uses variance ratio to detect mean-reversion tendency.
    """
    n = len(series)
    half_n = n // 2

    # Compare variance of first and second half
    var1 = np.var(series[:half_n])
    var2 = np.var(series[half_n:])

    # Variance ratio - stable variance suggests stationarity
    ratio = max(var1, var2) / max(min(var1, var2), 1e-10)

    # Heuristic: ratio close to 1 suggests stationarity
    is_stationary = ratio < 2.0

    # Approximate ADF statistic using difference variance
    diff = np.diff(series)
    adf_stat = -np.mean(series[:-1] * diff) / (np.std(series) * np.std(diff) + 1e-10)

    return ADFResult(
        adf_statistic=float(adf_stat),
        p_value=0.1 if is_stationary else 0.5,
        used_lag=1,
        n_obs=n,
        critical_values={"1%": -3.43, "5%": -2.86, "10%": -2.57},
        is_stationary=is_stationary,
    )


def calculate_hurst_exponent(
    series: list[float] | np.ndarray,
    min_lag: int = 2,
    max_lag: int | None = None,
) -> HurstResult:
    """
    Calculate Hurst exponent using R/S analysis.

    Hurst exponent H characterizes time series:
    - H < 0.5: Mean-reverting (anti-persistent)
    - H = 0.5: Random walk (geometric Brownian motion)
    - H > 0.5: Trending (persistent)

    Args:
        series: Time series data.
        min_lag: Minimum lag for R/S calculation.
        max_lag: Maximum lag (defaults to n/4).

    Returns:
        HurstResult with exponent and interpretation.
    """
    series = np.array(series)
    n = len(series)

    if n < 20:
        return HurstResult(
            hurst_exponent=0.5,
            interpretation="Insufficient data for Hurst estimation",
            is_mean_reverting=False,
            is_trending=False,
            is_random_walk=True,
        )

    max_lag = max_lag or n // 4

    # R/S analysis
    lags = []
    rs_values = []

    for lag in range(min_lag, min(max_lag, n // 2)):
        # Divide series into chunks
        n_chunks = n // lag
        if n_chunks < 2:
            break

        rs_chunk = []
        for i in range(n_chunks):
            chunk = series[i * lag:(i + 1) * lag]
            mean_chunk = np.mean(chunk)

            # Cumulative deviation from mean
            cumsum = np.cumsum(chunk - mean_chunk)
            r = np.max(cumsum) - np.min(cumsum)  # Range

            s = np.std(chunk)  # Standard deviation
            if s > 1e-10:
                rs_chunk.append(r / s)

        if rs_chunk:
            lags.append(lag)
            rs_values.append(np.mean(rs_chunk))

    if len(lags) < 2:
        return HurstResult(
            hurst_exponent=0.5,
            interpretation="Insufficient lags for Hurst estimation",
            is_mean_reverting=False,
            is_trending=False,
            is_random_walk=True,
        )

    # Log-log regression: log(R/S) = H * log(lag) + c
    log_lags = np.log(lags)
    log_rs = np.log(rs_values)

    # Simple linear regression
    n_points = len(log_lags)
    sum_x = np.sum(log_lags)
    sum_y = np.sum(log_rs)
    sum_xy = np.sum(log_lags * log_rs)
    sum_x2 = np.sum(log_lags ** 2)

    hurst = float((n_points * sum_xy - sum_x * sum_y) / (n_points * sum_x2 - sum_x ** 2))

    # Clamp to valid range [0, 1]
    hurst = max(0.0, min(1.0, hurst))

    # Interpretation
    if hurst < 0.4:
        interpretation = f"Strongly mean-reverting (H={hurst:.3f})"
        is_mean_reverting = True
        is_trending = False
        is_random_walk = False
    elif hurst < 0.5:
        interpretation = f"Weakly mean-reverting (H={hurst:.3f})"
        is_mean_reverting = True
        is_trending = False
        is_random_walk = False
    elif hurst < 0.55:
        interpretation = f"Random walk / no memory (H={hurst:.3f})"
        is_mean_reverting = False
        is_trending = False
        is_random_walk = True
    elif hurst < 0.7:
        interpretation = f"Weakly trending (H={hurst:.3f})"
        is_mean_reverting = False
        is_trending = True
        is_random_walk = False
    else:
        interpretation = f"Strongly trending (H={hurst:.3f})"
        is_mean_reverting = False
        is_trending = True
        is_random_walk = False

    return HurstResult(
        hurst_exponent=hurst,
        interpretation=interpretation,
        is_mean_reverting=is_mean_reverting,
        is_trending=is_trending,
        is_random_walk=is_random_walk,
    )


def calculate_half_life(
    series: list[float] | np.ndarray,
) -> HalfLifeResult:
    """
    Calculate half-life of mean reversion using Ornstein-Uhlenbeck model.

    Models series as: dX = theta * (mu - X) * dt + sigma * dW

    Half-life = ln(2) / theta

    Args:
        series: Time series data (should be spread or deviation from mean).

    Returns:
        HalfLifeResult with half-life estimation.
    """
    series = np.array(series)
    n = len(series)

    if n < 20:
        return HalfLifeResult(
            half_life=float("inf"),
            theta=0.0,
            mu=0.0,
            is_valid=False,
            interpretation="Insufficient data for half-life estimation",
        )

    # Lag series for regression
    y = series[1:]  # X_t
    x = series[:-1]  # X_{t-1}

    # Linear regression: X_t = alpha + beta * X_{t-1} + epsilon
    x_mean = np.mean(x)
    y_mean = np.mean(y)

    numerator = np.sum((x - x_mean) * (y - y_mean))
    denominator = np.sum((x - x_mean) ** 2)

    if abs(denominator) < 1e-10:
        return HalfLifeResult(
            half_life=float("inf"),
            theta=0.0,
            mu=float(np.mean(series)),
            is_valid=False,
            interpretation="Zero variance - cannot estimate half-life",
        )

    beta = numerator / denominator
    alpha = y_mean - beta * x_mean

    # theta = -ln(beta) for OU process (if beta > 0)
    if beta <= 0 or beta >= 1:
        return HalfLifeResult(
            half_life=float("inf"),
            theta=0.0,
            mu=float(np.mean(series)),
            is_valid=False,
            interpretation="Series is not mean-reverting (beta outside (0,1))",
        )

    theta = -np.log(beta)
    half_life = np.log(2) / theta

    # Long-term mean
    mu = alpha / (1 - beta)

    # Interpretation
    if half_life < 1:
        interpretation = f"Very fast mean-reversion: {half_life:.2f} periods"
    elif half_life < 5:
        interpretation = f"Fast mean-reversion: {half_life:.2f} periods"
    elif half_life < 20:
        interpretation = f"Moderate mean-reversion: {half_life:.2f} periods"
    elif half_life < 60:
        interpretation = f"Slow mean-reversion: {half_life:.2f} periods"
    else:
        interpretation = f"Very slow mean-reversion: {half_life:.2f} periods"

    return HalfLifeResult(
        half_life=float(half_life),
        theta=float(theta),
        mu=float(mu),
        is_valid=True,
        interpretation=interpretation,
    )


@dataclass
class StationarityTestSuite:
    """
    Combined stationarity test results.

    Attributes:
        adf: ADF test result.
        hurst: Hurst exponent result.
        half_life: Half-life result.
        overall_stationary: Combined assessment.
        recommendation: Trading recommendation.
    """

    adf: ADFResult
    hurst: HurstResult
    half_life: HalfLifeResult
    overall_stationary: bool
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "adf": self.adf.to_dict(),
            "hurst": self.hurst.to_dict(),
            "half_life": self.half_life.to_dict(),
            "overall_stationary": self.overall_stationary,
            "recommendation": self.recommendation,
        }


def run_stationarity_tests(
    series: list[float] | np.ndarray,
    max_acceptable_half_life: float = 30.0,
) -> StationarityTestSuite:
    """
    Run complete stationarity test suite.

    Args:
        series: Time series data.
        max_acceptable_half_life: Maximum acceptable half-life for trading.

    Returns:
        StationarityTestSuite with all test results.
    """
    adf = adf_test(series)
    hurst = calculate_hurst_exponent(series)
    half_life = calculate_half_life(series)

    # Combined assessment
    overall_stationary = (
        adf.is_stationary
        and hurst.is_mean_reverting
        and half_life.is_valid
        and half_life.half_life < max_acceptable_half_life
    )

    # Recommendation
    if overall_stationary:
        recommendation = (
            f"Series is suitable for mean-reversion trading. "
            f"Half-life: {half_life.half_life:.1f} periods"
        )
    elif adf.is_stationary and not hurst.is_mean_reverting:
        recommendation = (
            "Series is stationary but not strongly mean-reverting. "
            "Consider trend-following strategies."
        )
    elif half_life.half_life > max_acceptable_half_life:
        recommendation = (
            f"Half-life ({half_life.half_life:.1f}) exceeds limit ({max_acceptable_half_life}). "
            "Mean-reversion too slow for practical trading."
        )
    else:
        recommendation = (
            "Series does not appear stationary. "
            "Mean-reversion strategies not recommended."
        )

    return StationarityTestSuite(
        adf=adf,
        hurst=hurst,
        half_life=half_life,
        overall_stationary=overall_stationary,
        recommendation=recommendation,
    )
