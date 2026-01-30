"""
Signal Generation Utilities.

Provides signal generation classes for various trading strategies,
including EMA crossover, VPIN-based adverse selection, and Z-score
mean reversion signals.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any

import numpy as np


class SignalType(Enum):
    """Trading signal types."""

    LONG = auto()  # Go long / buy
    SHORT = auto()  # Go short / sell
    EXIT_LONG = auto()  # Exit long position
    EXIT_SHORT = auto()  # Exit short position
    FLAT = auto()  # No signal / stay flat
    REDUCE = auto()  # Reduce position size
    HOLD = auto()  # Hold current position


class SignalStrength(Enum):
    """Signal strength classification."""

    WEAK = auto()  # Low confidence signal
    MODERATE = auto()  # Medium confidence signal
    STRONG = auto()  # High confidence signal
    VERY_STRONG = auto()  # Very high confidence signal


@dataclass
class Signal:
    """
    Trading signal with metadata.

    Attributes:
        signal_type: The type of signal.
        strength: Signal strength/confidence.
        value: Raw signal value (e.g., z-score, VPIN).
        timestamp: When signal was generated.
        source: Signal source identifier.
        metadata: Additional signal metadata.
    """

    signal_type: SignalType
    strength: SignalStrength
    value: float
    timestamp: datetime
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_entry(self) -> bool:
        """Return True if this is an entry signal."""
        return self.signal_type in (SignalType.LONG, SignalType.SHORT)

    @property
    def is_exit(self) -> bool:
        """Return True if this is an exit signal."""
        return self.signal_type in (SignalType.EXIT_LONG, SignalType.EXIT_SHORT, SignalType.FLAT)

    @property
    def is_bullish(self) -> bool:
        """Return True if signal is bullish."""
        return self.signal_type in (SignalType.LONG, SignalType.EXIT_SHORT)

    @property
    def is_bearish(self) -> bool:
        """Return True if signal is bearish."""
        return self.signal_type in (SignalType.SHORT, SignalType.EXIT_LONG)


class SignalGenerator(ABC):
    """Abstract base class for signal generators."""

    def __init__(self, name: str) -> None:
        """
        Initialize signal generator.

        Args:
            name: Generator name/identifier.
        """
        self.name = name
        self._last_signal: Signal | None = None

    @property
    def last_signal(self) -> Signal | None:
        """Return the last generated signal."""
        return self._last_signal

    @abstractmethod
    def update(self, value: float, timestamp: datetime | None = None) -> Signal | None:
        """
        Update generator with new data and optionally generate signal.

        Args:
            value: New data value.
            timestamp: Timestamp for the value.

        Returns:
            Signal if generated, None otherwise.
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset generator state."""
        pass


class EMASignalGenerator(SignalGenerator):
    """
    EMA crossover signal generator.

    Generates signals based on fast EMA crossing slow EMA:
    - LONG when fast crosses above slow (bullish crossover)
    - SHORT when fast crosses below slow (bearish crossover)

    EMA formula:
        EMA_t = alpha * price_t + (1 - alpha) * EMA_{t-1}
        where alpha = 2 / (period + 1)
    """

    def __init__(
        self,
        fast_period: int = 10,
        slow_period: int = 20,
        name: str = "EMA_CROSS",
    ) -> None:
        """
        Initialize EMA signal generator.

        Args:
            fast_period: Fast EMA period.
            slow_period: Slow EMA period.
            name: Generator name.
        """
        super().__init__(name)

        if fast_period >= slow_period:
            raise ValueError("fast_period must be less than slow_period")

        self.fast_period = fast_period
        self.slow_period = slow_period

        # EMA state
        self._fast_alpha = 2.0 / (fast_period + 1)
        self._slow_alpha = 2.0 / (slow_period + 1)
        self._fast_ema: float | None = None
        self._slow_ema: float | None = None
        self._prev_fast_ema: float | None = None
        self._prev_slow_ema: float | None = None
        self._count = 0

    @property
    def fast_ema(self) -> float | None:
        """Return current fast EMA value."""
        return self._fast_ema

    @property
    def slow_ema(self) -> float | None:
        """Return current slow EMA value."""
        return self._slow_ema

    @property
    def is_initialized(self) -> bool:
        """Return True if EMAs are initialized."""
        return self._count >= self.slow_period

    def update(self, value: float, timestamp: datetime | None = None) -> Signal | None:
        """
        Update EMAs and check for crossover.

        Args:
            value: New price value.
            timestamp: Timestamp for the value.

        Returns:
            Signal on crossover, None otherwise.
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        self._count += 1

        # Initialize EMAs with first value
        if self._fast_ema is None:
            self._fast_ema = value
            self._slow_ema = value
            return None

        # Store previous values (guaranteed non-None after initialization check above)
        self._prev_fast_ema = self._fast_ema
        self._prev_slow_ema = self._slow_ema

        # Update EMAs: EMA = alpha * price + (1 - alpha) * prev_EMA
        # Note: _fast_ema and _slow_ema are guaranteed non-None here (would have returned above)
        assert self._fast_ema is not None and self._slow_ema is not None
        self._fast_ema = self._fast_alpha * value + (1 - self._fast_alpha) * self._fast_ema
        self._slow_ema = self._slow_alpha * value + (1 - self._slow_alpha) * self._slow_ema

        # Wait for initialization
        if not self.is_initialized:
            return None

        # Check for crossover
        signal = self._check_crossover(timestamp)
        if signal:
            self._last_signal = signal
        return signal

    def _check_crossover(self, timestamp: datetime) -> Signal | None:
        """Check for EMA crossover."""
        if self._prev_fast_ema is None or self._prev_slow_ema is None:
            return None
        if self._fast_ema is None or self._slow_ema is None:
            return None

        # Calculate signal value (spread between EMAs)
        spread = self._fast_ema - self._slow_ema
        # Safe division with explicit zero check
        spread_pct = spread / self._slow_ema if abs(self._slow_ema) > 1e-10 else 0.0

        # Determine signal strength based on spread magnitude
        abs_spread = abs(spread_pct)
        if abs_spread > 0.02:
            strength = SignalStrength.VERY_STRONG
        elif abs_spread > 0.01:
            strength = SignalStrength.STRONG
        elif abs_spread > 0.005:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # Bullish crossover: fast crosses above slow
        if self._prev_fast_ema <= self._prev_slow_ema and self._fast_ema > self._slow_ema:
            return Signal(
                signal_type=SignalType.LONG,
                strength=strength,
                value=spread_pct,
                timestamp=timestamp,
                source=self.name,
                metadata={
                    "fast_ema": self._fast_ema,
                    "slow_ema": self._slow_ema,
                    "crossover_type": "bullish",
                },
            )

        # Bearish crossover: fast crosses below slow
        if self._prev_fast_ema >= self._prev_slow_ema and self._fast_ema < self._slow_ema:
            return Signal(
                signal_type=SignalType.SHORT,
                strength=strength,
                value=spread_pct,
                timestamp=timestamp,
                source=self.name,
                metadata={
                    "fast_ema": self._fast_ema,
                    "slow_ema": self._slow_ema,
                    "crossover_type": "bearish",
                },
            )

        return None

    def reset(self) -> None:
        """Reset EMA state."""
        self._fast_ema = None
        self._slow_ema = None
        self._prev_fast_ema = None
        self._prev_slow_ema = None
        self._count = 0
        self._last_signal = None


class VPINSignalGenerator(SignalGenerator):
    """
    VPIN (Volume-Synchronized Probability of Informed Trading) signal generator.

    VPIN measures order flow toxicity:
        VPIN = |Buy Volume - Sell Volume| / Total Volume

    High VPIN indicates potential adverse selection (informed trading).

    Generates signals:
    - FLAT when VPIN exceeds threshold (pull quotes)
    - HOLD when VPIN is within normal range
    """

    def __init__(
        self,
        bucket_size: float = 1000.0,
        num_buckets: int = 50,
        threshold: float = 0.7,
        name: str = "VPIN",
    ) -> None:
        """
        Initialize VPIN signal generator.

        Args:
            bucket_size: Volume per bucket.
            num_buckets: Number of buckets for VPIN calculation.
            threshold: VPIN threshold for adverse selection.
            name: Generator name.
        """
        super().__init__(name)

        self.bucket_size = bucket_size
        self.num_buckets = num_buckets
        self.threshold = threshold

        # Volume tracking
        self._buy_volume = 0.0
        self._sell_volume = 0.0
        self._vpin_buckets: list[float] = []
        self._current_vpin = 0.0

    @property
    def vpin(self) -> float:
        """Return current VPIN value."""
        return self._current_vpin

    @property
    def is_toxic(self) -> bool:
        """Return True if current VPIN exceeds threshold."""
        return self._current_vpin >= self.threshold

    def add_trade(
        self,
        size: float,
        is_buyer_aggressor: bool,
        timestamp: datetime | None = None,
    ) -> Signal | None:
        """
        Add trade to VPIN calculation.

        Args:
            size: Trade size.
            is_buyer_aggressor: True if buyer was aggressor.
            timestamp: Trade timestamp.

        Returns:
            Signal if VPIN state changes significantly.
        """
        # Classify volume
        if is_buyer_aggressor:
            self._buy_volume += size
        else:
            self._sell_volume += size

        total = self._buy_volume + self._sell_volume

        # Check if bucket is full
        if total >= self.bucket_size:
            # Calculate VPIN for this bucket: |Buy - Sell| / Total
            bucket_vpin = abs(self._buy_volume - self._sell_volume) / total
            self._vpin_buckets.append(bucket_vpin)

            # Maintain bucket window
            if len(self._vpin_buckets) > self.num_buckets:
                self._vpin_buckets.pop(0)

            # Reset for next bucket
            self._buy_volume = 0.0
            self._sell_volume = 0.0

        # Update current VPIN (average over buckets)
        if self._vpin_buckets:
            self._current_vpin = np.mean(self._vpin_buckets)

        return self.update(self._current_vpin, timestamp)

    def update(self, value: float, timestamp: datetime | None = None) -> Signal | None:
        """
        Update with direct VPIN value.

        Args:
            value: VPIN value.
            timestamp: Timestamp.

        Returns:
            Signal based on VPIN level.
        """
        timestamp = timestamp or datetime.now(timezone.utc)
        self._current_vpin = value

        # Determine signal strength
        if value >= 0.9:
            strength = SignalStrength.VERY_STRONG
        elif value >= 0.8:
            strength = SignalStrength.STRONG
        elif value >= 0.7:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        # High VPIN - adverse selection risk
        if value >= self.threshold:
            signal = Signal(
                signal_type=SignalType.FLAT,
                strength=strength,
                value=value,
                timestamp=timestamp,
                source=self.name,
                metadata={
                    "threshold": self.threshold,
                    "reason": "adverse_selection_risk",
                    "num_buckets": len(self._vpin_buckets),
                },
            )
            self._last_signal = signal
            return signal

        return None

    def reset(self) -> None:
        """Reset VPIN state."""
        self._buy_volume = 0.0
        self._sell_volume = 0.0
        self._vpin_buckets.clear()
        self._current_vpin = 0.0
        self._last_signal = None


class ZScoreSignalGenerator(SignalGenerator):
    """
    Z-score based mean reversion signal generator.

    Used for pairs trading and mean reversion strategies.

    Z-score formula:
        z = (x - mean) / std

    Generates signals:
    - LONG when z-score < -entry_threshold (spread too low)
    - SHORT when z-score > entry_threshold (spread too high)
    - EXIT when |z-score| < exit_threshold
    """

    def __init__(
        self,
        lookback_period: int = 20,
        entry_threshold: float = 2.0,
        exit_threshold: float = 0.5,
        stop_threshold: float = 4.0,
        name: str = "ZSCORE",
    ) -> None:
        """
        Initialize Z-score signal generator.

        Args:
            lookback_period: Period for mean/std calculation.
            entry_threshold: Z-score threshold for entry.
            exit_threshold: Z-score threshold for exit.
            stop_threshold: Z-score threshold for stop loss.
            name: Generator name.
        """
        super().__init__(name)

        self.lookback_period = lookback_period
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.stop_threshold = stop_threshold

        # State
        self._values: list[float] = []
        self._zscore: float | None = None
        self._mean: float | None = None
        self._std: float | None = None
        self._position: int = 0  # 1 = long, -1 = short, 0 = flat

    @property
    def zscore(self) -> float | None:
        """Return current z-score."""
        return self._zscore

    @property
    def mean(self) -> float | None:
        """Return current mean."""
        return self._mean

    @property
    def std(self) -> float | None:
        """Return current standard deviation."""
        return self._std

    @property
    def is_initialized(self) -> bool:
        """Return True if enough data for z-score calculation."""
        return len(self._values) >= self.lookback_period

    def set_position(self, position: int) -> None:
        """
        Set current position state.

        Args:
            position: 1 for long, -1 for short, 0 for flat.
        """
        self._position = position

    def update(self, value: float, timestamp: datetime | None = None) -> Signal | None:
        """
        Update with new spread value and check for signals.

        Args:
            value: New spread value.
            timestamp: Timestamp.

        Returns:
            Signal based on z-score.
        """
        timestamp = timestamp or datetime.now(timezone.utc)

        # Update value history
        self._values.append(value)
        if len(self._values) > self.lookback_period:
            self._values.pop(0)

        # Need enough data
        if not self.is_initialized:
            return None

        # Calculate z-score
        self._mean = float(np.mean(self._values))
        self._std = float(np.std(self._values))

        if self._std < 1e-10:
            return None

        self._zscore = (value - self._mean) / self._std

        # Generate signal
        signal = self._check_signal(timestamp)
        if signal:
            self._last_signal = signal
        return signal

    def _check_signal(self, timestamp: datetime) -> Signal | None:
        """Check for z-score based signals."""
        z = self._zscore
        if z is None:
            return None

        # Determine signal strength
        abs_z = abs(z)
        if abs_z >= 3.0:
            strength = SignalStrength.VERY_STRONG
        elif abs_z >= 2.5:
            strength = SignalStrength.STRONG
        elif abs_z >= 2.0:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK

        metadata = {
            "zscore": z,
            "mean": self._mean,
            "std": self._std,
            "entry_threshold": self.entry_threshold,
            "exit_threshold": self.exit_threshold,
        }

        # Stop loss check
        if abs_z > self.stop_threshold:
            if self._position == 1:
                return Signal(
                    signal_type=SignalType.EXIT_LONG,
                    strength=SignalStrength.VERY_STRONG,
                    value=z,
                    timestamp=timestamp,
                    source=self.name,
                    metadata={**metadata, "reason": "stop_loss"},
                )
            elif self._position == -1:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    strength=SignalStrength.VERY_STRONG,
                    value=z,
                    timestamp=timestamp,
                    source=self.name,
                    metadata={**metadata, "reason": "stop_loss"},
                )

        # Exit signals (mean reversion complete)
        if self._position != 0 and abs_z < self.exit_threshold:
            if self._position == 1:
                return Signal(
                    signal_type=SignalType.EXIT_LONG,
                    strength=strength,
                    value=z,
                    timestamp=timestamp,
                    source=self.name,
                    metadata={**metadata, "reason": "exit_threshold"},
                )
            elif self._position == -1:
                return Signal(
                    signal_type=SignalType.EXIT_SHORT,
                    strength=strength,
                    value=z,
                    timestamp=timestamp,
                    source=self.name,
                    metadata={**metadata, "reason": "exit_threshold"},
                )

        # Entry signals (only when flat)
        # Note: z is guaranteed non-None here due to early return at start of _check_signal
        if self._position == 0:
            # Spread too high - short spread
            if z > self.entry_threshold:
                return Signal(
                    signal_type=SignalType.SHORT,
                    strength=strength,
                    value=z,
                    timestamp=timestamp,
                    source=self.name,
                    metadata={**metadata, "reason": "zscore_high"},
                )
            # Spread too low - long spread
            if z < -self.entry_threshold:
                return Signal(
                    signal_type=SignalType.LONG,
                    strength=strength,
                    value=z,
                    timestamp=timestamp,
                    source=self.name,
                    metadata={**metadata, "reason": "zscore_low"},
                )

        return None

    def reset(self) -> None:
        """Reset z-score state."""
        self._values.clear()
        self._zscore = None
        self._mean = None
        self._std = None
        self._position = 0
        self._last_signal = None


class CompositeSignalGenerator(SignalGenerator):
    """
    Composite signal generator that combines multiple signal sources.

    Supports various aggregation methods:
    - unanimous: All generators must agree
    - majority: Majority of generators agree
    - weighted: Weighted combination of signals
    - any: Any generator signals
    """

    def __init__(
        self,
        generators: list[SignalGenerator],
        weights: list[float] | None = None,
        method: str = "majority",
        name: str = "COMPOSITE",
    ) -> None:
        """
        Initialize composite signal generator.

        Args:
            generators: List of signal generators.
            weights: Optional weights for each generator.
            method: Aggregation method (unanimous, majority, weighted, any).
            name: Generator name.
        """
        super().__init__(name)

        if not generators:
            raise ValueError("At least one generator required")

        self.generators = generators
        self.method = method

        if weights is None:
            self.weights = [1.0 / len(generators)] * len(generators)
        else:
            if len(weights) != len(generators):
                raise ValueError("Weights must match number of generators")
            total = sum(weights)
            self.weights = [w / total for w in weights]

        self._signals: list[Signal | None] = [None] * len(generators)

    def update(self, value: float, timestamp: datetime | None = None) -> Signal | None:
        """
        Update all generators and aggregate signals.

        Args:
            value: New value (passed to all generators).
            timestamp: Timestamp.

        Returns:
            Aggregated signal based on method.
        """
        timestamp = timestamp or datetime.now(timezone.utc)

        # Update each generator
        for i, gen in enumerate(self.generators):
            self._signals[i] = gen.update(value, timestamp)

        # Aggregate signals
        return self._aggregate_signals(timestamp)

    def update_generator(
        self,
        index: int,
        value: float,
        timestamp: datetime | None = None,
    ) -> Signal | None:
        """
        Update a specific generator.

        Args:
            index: Generator index.
            value: New value.
            timestamp: Timestamp.

        Returns:
            Aggregated signal after update.
        """
        timestamp = timestamp or datetime.now(timezone.utc)

        if 0 <= index < len(self.generators):
            self._signals[index] = self.generators[index].update(value, timestamp)

        return self._aggregate_signals(timestamp)

    def _aggregate_signals(self, timestamp: datetime) -> Signal | None:
        """Aggregate signals based on method."""
        # Filter out None signals
        valid_signals = [(i, s) for i, s in enumerate(self._signals) if s is not None]

        if not valid_signals:
            return None

        if self.method == "unanimous":
            return self._unanimous(valid_signals, timestamp)
        elif self.method == "majority":
            return self._majority(valid_signals, timestamp)
        elif self.method == "weighted":
            return self._weighted(valid_signals, timestamp)
        elif self.method == "any":
            return self._any(valid_signals, timestamp)
        else:
            raise ValueError(f"Unknown aggregation method: {self.method}")

    def _unanimous(
        self,
        signals: list[tuple[int, Signal]],
        timestamp: datetime,
    ) -> Signal | None:
        """All signals must agree."""
        if len(signals) != len(self.generators):
            return None

        signal_types = {s.signal_type for _, s in signals}
        if len(signal_types) != 1:
            return None

        # All agree - return combined signal
        signal_type = signals[0][1].signal_type
        avg_value = np.mean([s.value for _, s in signals])

        return Signal(
            signal_type=signal_type,
            strength=SignalStrength.VERY_STRONG,
            value=avg_value,
            timestamp=timestamp,
            source=self.name,
            metadata={"method": "unanimous", "sources": [s.source for _, s in signals]},
        )

    def _majority(
        self,
        signals: list[tuple[int, Signal]],
        timestamp: datetime,
    ) -> Signal | None:
        """Majority of signals must agree."""
        # Count signal types
        type_counts: dict[SignalType, list[Signal]] = {}
        for _, s in signals:
            if s.signal_type not in type_counts:
                type_counts[s.signal_type] = []
            type_counts[s.signal_type].append(s)

        # Find majority
        for signal_type, sigs in type_counts.items():
            if len(sigs) > len(self.generators) / 2:
                avg_value = np.mean([s.value for s in sigs])
                return Signal(
                    signal_type=signal_type,
                    strength=SignalStrength.STRONG,
                    value=avg_value,
                    timestamp=timestamp,
                    source=self.name,
                    metadata={
                        "method": "majority",
                        "count": len(sigs),
                        "sources": [s.source for s in sigs],
                    },
                )

        return None

    def _weighted(
        self,
        signals: list[tuple[int, Signal]],
        timestamp: datetime,
    ) -> Signal | None:
        """Weighted combination of signals."""
        # Calculate weighted score for bullish/bearish
        bullish_weight = 0.0
        bearish_weight = 0.0
        total_value = 0.0

        for i, s in signals:
            weight = self.weights[i]
            if s.is_bullish:
                bullish_weight += weight
            elif s.is_bearish:
                bearish_weight += weight
            total_value += s.value * weight

        # Determine signal
        threshold = 0.5
        if bullish_weight > threshold and bullish_weight > bearish_weight:
            signal_type = SignalType.LONG
            strength = SignalStrength.STRONG if bullish_weight > 0.7 else SignalStrength.MODERATE
        elif bearish_weight > threshold and bearish_weight > bullish_weight:
            signal_type = SignalType.SHORT
            strength = SignalStrength.STRONG if bearish_weight > 0.7 else SignalStrength.MODERATE
        else:
            return None

        return Signal(
            signal_type=signal_type,
            strength=strength,
            value=total_value,
            timestamp=timestamp,
            source=self.name,
            metadata={
                "method": "weighted",
                "bullish_weight": bullish_weight,
                "bearish_weight": bearish_weight,
            },
        )

    def _any(
        self,
        signals: list[tuple[int, Signal]],
        timestamp: datetime,
    ) -> Signal | None:
        """Any signal triggers."""
        # Return strongest signal
        strongest = max(signals, key=lambda x: x[1].strength.value)
        _, signal = strongest

        return Signal(
            signal_type=signal.signal_type,
            strength=signal.strength,
            value=signal.value,
            timestamp=timestamp,
            source=self.name,
            metadata={"method": "any", "original_source": signal.source},
        )

    def reset(self) -> None:
        """Reset all generators."""
        for gen in self.generators:
            gen.reset()
        self._signals = [None] * len(self.generators)
        self._last_signal = None
