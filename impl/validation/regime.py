"""
Regime Detection Module.

Provides market regime detection using Hidden Markov Models
and regime-conditional performance analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


class RegimeType:
    """Market regime types."""

    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"
    HIGH_VOL = "high_volatility"
    LOW_VOL = "low_volatility"


@dataclass
class RegimeState:
    """
    Single regime state definition.

    Attributes:
        name: Regime name.
        mean_return: Expected return in this regime.
        volatility: Volatility in this regime.
        duration: Average duration in periods.
    """

    name: str
    mean_return: float
    volatility: float
    duration: float


@dataclass
class RegimeDetectionResult:
    """
    Regime detection result.

    Attributes:
        regimes: List of detected regimes.
        regime_sequence: Regime assignment for each period.
        regime_probabilities: Probability of each regime per period.
        transition_matrix: Regime transition probabilities.
        current_regime: Most likely current regime.
        regime_stats: Statistics for each regime.
    """

    regimes: list[RegimeState]
    regime_sequence: list[str]
    regime_probabilities: list[dict[str, float]]
    transition_matrix: dict[str, dict[str, float]]
    current_regime: str
    regime_stats: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "regimes": [
                {"name": r.name, "mean_return": r.mean_return, "volatility": r.volatility}
                for r in self.regimes
            ],
            "current_regime": self.current_regime,
            "regime_stats": self.regime_stats,
            "transition_matrix": self.transition_matrix,
        }


@dataclass
class RegimePerformance:
    """
    Strategy performance by regime.

    Attributes:
        regime: Regime name.
        total_return: Total return in regime.
        sharpe_ratio: Sharpe ratio in regime.
        max_drawdown: Max drawdown in regime.
        trade_count: Number of trades in regime.
        win_rate: Win rate in regime.
        avg_duration_periods: Average time in regime.
    """

    regime: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    trade_count: int
    win_rate: float
    avg_duration_periods: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "regime": self.regime,
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "trade_count": self.trade_count,
            "win_rate": self.win_rate,
            "avg_duration_periods": self.avg_duration_periods,
        }


def _calculate_regime_durations(
    regime_sequence: list[str],
    target_regime: str,
) -> list[int]:
    """
    Calculate durations of consecutive periods in a specific regime.

    Args:
        regime_sequence: List of regime labels.
        target_regime: Regime to calculate durations for.

    Returns:
        List of duration lengths for each occurrence of the regime.
    """
    durations: list[int] = []
    current_duration = 0

    for regime in regime_sequence:
        if regime == target_regime:
            current_duration += 1
        else:
            if current_duration > 0:
                durations.append(current_duration)
            current_duration = 0

    # Don't forget the last run
    if current_duration > 0:
        durations.append(current_duration)

    return durations


class SimpleRegimeDetector:
    """
    Simple regime detector using rolling statistics.

    Uses rolling mean and volatility to classify regimes
    without requiring HMM libraries.
    """

    def __init__(
        self,
        lookback_period: int = 20,
        vol_threshold_low: float = 0.5,
        vol_threshold_high: float = 1.5,
        trend_threshold: float = 0.0,
    ) -> None:
        """
        Initialize regime detector.

        Args:
            lookback_period: Period for rolling calculations.
            vol_threshold_low: Volatility threshold for low vol regime (as fraction of mean).
            vol_threshold_high: Volatility threshold for high vol regime.
            trend_threshold: Return threshold for trend detection.
        """
        self.lookback_period = lookback_period
        self.vol_threshold_low = vol_threshold_low
        self.vol_threshold_high = vol_threshold_high
        self.trend_threshold = trend_threshold

    def detect_regimes(
        self,
        returns: list[float] | np.ndarray,
    ) -> RegimeDetectionResult:
        """
        Detect market regimes from returns.

        Args:
            returns: Return series.

        Returns:
            RegimeDetectionResult with detected regimes.
        """
        returns = np.array(returns)
        n = len(returns)

        if n < self.lookback_period:
            # Not enough data
            return self._create_single_regime_result(returns, RegimeType.SIDEWAYS)

        # Calculate rolling statistics
        rolling_mean = np.array([
            np.mean(returns[max(0, i - self.lookback_period):i + 1])
            for i in range(n)
        ])
        rolling_vol = np.array([
            np.std(returns[max(0, i - self.lookback_period):i + 1])
            for i in range(n)
        ])

        # Calculate overall statistics
        overall_vol = np.std(returns)
        if overall_vol < 1e-10:
            overall_vol = 1.0

        # Classify each period
        regime_sequence = []
        for i in range(n):
            vol_ratio = rolling_vol[i] / overall_vol

            if vol_ratio < self.vol_threshold_low:
                if rolling_mean[i] > self.trend_threshold:
                    regime = RegimeType.BULL
                elif rolling_mean[i] < -self.trend_threshold:
                    regime = RegimeType.BEAR
                else:
                    regime = RegimeType.LOW_VOL
            elif vol_ratio > self.vol_threshold_high:
                regime = RegimeType.HIGH_VOL
            else:
                if rolling_mean[i] > self.trend_threshold * 2:
                    regime = RegimeType.BULL
                elif rolling_mean[i] < -self.trend_threshold * 2:
                    regime = RegimeType.BEAR
                else:
                    regime = RegimeType.SIDEWAYS

            regime_sequence.append(regime)

        # Calculate regime statistics
        regime_stats = self._calculate_regime_stats(returns, regime_sequence)

        # Calculate transition matrix
        transition_matrix = self._calculate_transition_matrix(regime_sequence)

        # Create regime states
        regimes = []
        for regime_name, stats in regime_stats.items():
            regimes.append(RegimeState(
                name=regime_name,
                mean_return=stats["mean_return"],
                volatility=stats["volatility"],
                duration=stats["avg_duration"],
            ))

        # Regime probabilities (simple - just current regime)
        regime_probabilities = []
        unique_regimes = list(set(regime_sequence))
        for regime in regime_sequence:
            probs = {r: 0.0 for r in unique_regimes}
            probs[regime] = 1.0
            regime_probabilities.append(probs)

        return RegimeDetectionResult(
            regimes=regimes,
            regime_sequence=regime_sequence,
            regime_probabilities=regime_probabilities,
            transition_matrix=transition_matrix,
            current_regime=regime_sequence[-1],
            regime_stats=regime_stats,
        )

    def _calculate_regime_stats(
        self,
        returns: np.ndarray,
        regime_sequence: list[str],
    ) -> dict[str, dict[str, float]]:
        """Calculate statistics for each regime."""
        stats: dict[str, dict[str, float]] = {}

        unique_regimes = set(regime_sequence)

        for regime in unique_regimes:
            mask = np.array([r == regime for r in regime_sequence])
            regime_returns = returns[mask]

            if len(regime_returns) == 0:
                continue

            # Calculate average duration using helper
            durations = _calculate_regime_durations(regime_sequence, regime)
            avg_duration = float(np.mean(durations)) if durations else 0.0

            stats[regime] = {
                "mean_return": float(np.mean(regime_returns)),
                "volatility": float(np.std(regime_returns)),
                "count": int(np.sum(mask)),
                "avg_duration": float(avg_duration),
                "total_return": float(np.sum(regime_returns)),
            }

        return stats

    def _calculate_transition_matrix(
        self,
        regime_sequence: list[str],
    ) -> dict[str, dict[str, float]]:
        """Calculate regime transition probabilities."""
        if len(regime_sequence) < 2:
            return {}

        unique_regimes = list(set(regime_sequence))
        transition_counts: dict[str, dict[str, int]] = {
            r: {r2: 0 for r2 in unique_regimes} for r in unique_regimes
        }

        for i in range(len(regime_sequence) - 1):
            from_regime = regime_sequence[i]
            to_regime = regime_sequence[i + 1]
            transition_counts[from_regime][to_regime] += 1

        # Convert to probabilities
        transition_matrix: dict[str, dict[str, float]] = {}
        for from_regime, to_counts in transition_counts.items():
            total = sum(to_counts.values())
            if total > 0:
                transition_matrix[from_regime] = {
                    to_regime: count / total
                    for to_regime, count in to_counts.items()
                }
            else:
                transition_matrix[from_regime] = {r: 0.0 for r in unique_regimes}

        return transition_matrix

    def _create_single_regime_result(
        self,
        returns: np.ndarray,
        regime: str,
    ) -> RegimeDetectionResult:
        """Create result with single regime (insufficient data)."""
        return RegimeDetectionResult(
            regimes=[RegimeState(
                name=regime,
                mean_return=float(np.mean(returns)) if len(returns) > 0 else 0.0,
                volatility=float(np.std(returns)) if len(returns) > 1 else 0.0,
                duration=float(len(returns)),
            )],
            regime_sequence=[regime] * len(returns),
            regime_probabilities=[{regime: 1.0}] * len(returns),
            transition_matrix={regime: {regime: 1.0}},
            current_regime=regime,
            regime_stats={regime: {
                "mean_return": float(np.mean(returns)) if len(returns) > 0 else 0.0,
                "volatility": float(np.std(returns)) if len(returns) > 1 else 0.0,
                "count": len(returns),
                "avg_duration": float(len(returns)),
            }},
        )


class HMMRegimeDetector:
    """
    Hidden Markov Model regime detector.

    Uses Gaussian HMM to detect market regimes.
    Requires hmmlearn library.
    """

    def __init__(
        self,
        n_regimes: int = 3,
        n_iter: int = 100,
        random_seed: int = 42,
    ) -> None:
        """
        Initialize HMM regime detector.

        Args:
            n_regimes: Number of hidden states.
            n_iter: Maximum EM iterations.
            random_seed: Random seed for reproducibility.
        """
        self.n_regimes = n_regimes
        self.n_iter = n_iter
        self.random_seed = random_seed
        self._model = None
        self._regime_names: list[str] = []

    def fit(self, returns: list[float] | np.ndarray) -> None:
        """
        Fit HMM to returns data.

        Args:
            returns: Return series.
        """
        returns = np.array(returns).reshape(-1, 1)

        try:
            from hmmlearn import hmm

            self._model = hmm.GaussianHMM(
                n_components=self.n_regimes,
                covariance_type="full",
                n_iter=self.n_iter,
                random_state=self.random_seed,
            )
            self._model.fit(returns)

            # Name regimes by mean return
            means = self._model.means_.flatten()
            sorted_indices = np.argsort(means)

            self._regime_names = [""] * self.n_regimes
            if self.n_regimes == 2:
                self._regime_names[sorted_indices[0]] = RegimeType.BEAR
                self._regime_names[sorted_indices[1]] = RegimeType.BULL
            elif self.n_regimes == 3:
                self._regime_names[sorted_indices[0]] = RegimeType.BEAR
                self._regime_names[sorted_indices[1]] = RegimeType.SIDEWAYS
                self._regime_names[sorted_indices[2]] = RegimeType.BULL
            else:
                for i, idx in enumerate(sorted_indices):
                    self._regime_names[idx] = f"regime_{i}"

        except ImportError:
            # Fallback to simple detector
            self._model = None

    def detect_regimes(
        self,
        returns: list[float] | np.ndarray,
    ) -> RegimeDetectionResult:
        """
        Detect regimes using fitted HMM.

        Args:
            returns: Return series.

        Returns:
            RegimeDetectionResult with detected regimes.
        """
        returns = np.array(returns)

        if self._model is None:
            # Fallback to simple detector
            simple_detector = SimpleRegimeDetector()
            return simple_detector.detect_regimes(returns)

        returns_2d = returns.reshape(-1, 1)

        # Predict regime sequence
        hidden_states = self._model.predict(returns_2d)
        regime_sequence = [self._regime_names[s] for s in hidden_states]

        # Get probabilities
        probs = self._model.predict_proba(returns_2d)
        regime_probabilities = []
        for i in range(len(probs)):
            prob_dict = {}
            for j, name in enumerate(self._regime_names):
                prob_dict[name] = float(probs[i, j])
            regime_probabilities.append(prob_dict)

        # Create regime states
        regimes = []
        means = self._model.means_.flatten()
        covars = self._model.covars_

        for i, name in enumerate(self._regime_names):
            regimes.append(RegimeState(
                name=name,
                mean_return=float(means[i]),
                volatility=float(np.sqrt(covars[i, 0, 0])),
                duration=1.0 / (1.0 - self._model.transmat_[i, i]),
            ))

        # Transition matrix
        transition_matrix: dict[str, dict[str, float]] = {}
        for i, from_name in enumerate(self._regime_names):
            transition_matrix[from_name] = {}
            for j, to_name in enumerate(self._regime_names):
                transition_matrix[from_name][to_name] = float(self._model.transmat_[i, j])

        # Calculate regime stats
        simple_detector = SimpleRegimeDetector()
        regime_stats = simple_detector._calculate_regime_stats(returns, regime_sequence)

        return RegimeDetectionResult(
            regimes=regimes,
            regime_sequence=regime_sequence,
            regime_probabilities=regime_probabilities,
            transition_matrix=transition_matrix,
            current_regime=regime_sequence[-1] if regime_sequence else RegimeType.SIDEWAYS,
            regime_stats=regime_stats,
        )


def analyze_regime_performance(
    returns: list[float] | np.ndarray,
    regime_sequence: list[str],
    trades: list[dict[str, Any]] | None = None,
) -> dict[str, RegimePerformance]:
    """
    Analyze strategy performance by regime.

    Args:
        returns: Strategy returns.
        regime_sequence: Regime assignment for each period.
        trades: Optional list of trades with regime info.

    Returns:
        Dictionary of regime -> RegimePerformance.
    """
    returns = np.array(returns)

    if len(returns) != len(regime_sequence):
        raise ValueError("Returns and regime_sequence must have same length")

    unique_regimes = set(regime_sequence)
    performance: dict[str, RegimePerformance] = {}

    for regime in unique_regimes:
        mask = np.array([r == regime for r in regime_sequence])
        regime_returns = returns[mask]

        if len(regime_returns) == 0:
            continue

        total_return = float(np.sum(regime_returns))

        # Sharpe ratio
        mean_ret = np.mean(regime_returns)
        std_ret = np.std(regime_returns)
        sharpe = float(mean_ret / std_ret * np.sqrt(252)) if std_ret > 1e-10 else 0.0

        # Max drawdown
        cumulative = np.cumsum(regime_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = running_max - cumulative
        max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        # Trade stats if available
        trade_count = 0
        win_rate = 0.0
        if trades:
            regime_trades = [t for t in trades if t.get("regime") == regime]
            trade_count = len(regime_trades)
            wins = sum(1 for t in regime_trades if t.get("pnl", 0) > 0)
            win_rate = wins / trade_count if trade_count > 0 else 0.0

        # Average duration using helper
        durations = _calculate_regime_durations(regime_sequence, regime)
        avg_duration = float(np.mean(durations)) if durations else 0.0

        performance[regime] = RegimePerformance(
            regime=regime,
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            trade_count=trade_count,
            win_rate=win_rate,
            avg_duration_periods=avg_duration,
        )

    return performance
