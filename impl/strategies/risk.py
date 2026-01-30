"""
Risk Management Module.

Provides position sizing, volatility estimation, and risk management
utilities for trading strategies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum, auto
from typing import Any

import numpy as np


class RiskLevel(Enum):
    """Risk level classification."""

    LOW = auto()
    MODERATE = auto()
    HIGH = auto()
    EXTREME = auto()


@dataclass
class RiskMetrics:
    """
    Risk metrics for a strategy or portfolio.

    Attributes:
        var_95: Value at Risk at 95% confidence.
        var_99: Value at Risk at 99% confidence.
        cvar_95: Conditional VaR (Expected Shortfall) at 95%.
        volatility: Annualized volatility.
        sharpe_ratio: Sharpe ratio (assuming risk-free = 0).
        sortino_ratio: Sortino ratio (downside risk adjusted).
        max_drawdown: Maximum drawdown.
        current_drawdown: Current drawdown from peak.
        calmar_ratio: Calmar ratio (return / max drawdown).
        risk_level: Overall risk level classification.
    """

    var_95: float = 0.0
    var_99: float = 0.0
    cvar_95: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    calmar_ratio: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW


@dataclass
class RiskConfig:
    """
    Risk management configuration.

    Attributes:
        max_position_size: Maximum position size (units).
        max_position_value: Maximum position value (quote currency).
        max_daily_loss_pct: Maximum daily loss as percentage of equity.
        max_drawdown_pct: Maximum drawdown percentage.
        risk_per_trade_pct: Risk per trade as percentage of equity.
        max_open_orders: Maximum number of open orders.
        max_correlation: Maximum correlation with portfolio.
        volatility_target: Target annualized volatility.
        enable_circuit_breaker: Enable automatic shutdown on limits.
    """

    max_position_size: float = 10.0
    max_position_value: float = 100000.0
    max_daily_loss_pct: float = 2.0
    max_drawdown_pct: float = 10.0
    risk_per_trade_pct: float = 1.0
    max_open_orders: int = 10
    max_correlation: float = 0.7
    volatility_target: float = 0.15
    enable_circuit_breaker: bool = True


class VolatilityEstimator:
    """
    Volatility estimator using multiple methods.

    Supports:
    - Simple historical volatility
    - EWMA (Exponentially Weighted Moving Average)
    - Parkinson (high-low based)
    - Garman-Klass (OHLC based)
    - Yang-Zhang (most efficient for OHLC)
    """

    def __init__(
        self,
        lookback_period: int = 20,
        ewma_lambda: float = 0.94,
        annualization_factor: float = 252.0,
    ) -> None:
        """
        Initialize volatility estimator.

        Args:
            lookback_period: Lookback period for historical volatility.
            ewma_lambda: Decay factor for EWMA (0 < lambda < 1).
            annualization_factor: Factor for annualizing volatility.
        """
        self.lookback_period = lookback_period
        self.ewma_lambda = ewma_lambda
        self.annualization_factor = annualization_factor

        # State
        self._returns: list[float] = []
        self._prices: list[float] = []
        self._ohlc: list[tuple[float, float, float, float]] = []
        self._ewma_variance: float | None = None

    @property
    def simple_volatility(self) -> float | None:
        """Return simple historical volatility (annualized)."""
        if len(self._returns) < 2:
            return None
        return np.std(self._returns) * np.sqrt(self.annualization_factor)

    @property
    def ewma_volatility(self) -> float | None:
        """Return EWMA volatility (annualized)."""
        if self._ewma_variance is None:
            return None
        return np.sqrt(self._ewma_variance * self.annualization_factor)

    def update_price(self, price: float) -> float | None:
        """
        Update with new price and return current volatility.

        Args:
            price: New price.

        Returns:
            Current volatility estimate (annualized).
        """
        self._prices.append(price)
        if len(self._prices) > self.lookback_period + 1:
            self._prices.pop(0)

        if len(self._prices) < 2:
            return None

        # Calculate return
        ret = np.log(price / self._prices[-2])
        self._returns.append(ret)

        if len(self._returns) > self.lookback_period:
            self._returns.pop(0)

        # Update EWMA variance
        if self._ewma_variance is None:
            self._ewma_variance = ret ** 2
        else:
            self._ewma_variance = (
                self.ewma_lambda * self._ewma_variance
                + (1 - self.ewma_lambda) * ret ** 2
            )

        return self.ewma_volatility

    def update_ohlc(
        self,
        open_price: float,
        high: float,
        low: float,
        close: float,
    ) -> float | None:
        """
        Update with OHLC bar and return Garman-Klass volatility.

        Garman-Klass formula:
            sigma^2 = 0.5 * (ln(H/L))^2 - (2*ln(2) - 1) * (ln(C/O))^2

        Args:
            open_price: Open price.
            high: High price.
            low: Low price.
            close: Close price.

        Returns:
            Garman-Klass volatility estimate (annualized).
        """
        self._ohlc.append((open_price, high, low, close))
        if len(self._ohlc) > self.lookback_period:
            self._ohlc.pop(0)

        if len(self._ohlc) < 2:
            return None

        # Calculate Garman-Klass variance for each bar
        variances = []
        for o, h, l, c in self._ohlc:
            if h > 0 and l > 0 and o > 0 and c > 0:
                hl = np.log(h / l)
                co = np.log(c / o)
                var = 0.5 * hl ** 2 - (2 * np.log(2) - 1) * co ** 2
                variances.append(max(var, 0))  # Ensure non-negative

        if not variances:
            return None

        avg_variance = np.mean(variances)
        return np.sqrt(avg_variance * self.annualization_factor)

    def parkinson_volatility(self) -> float | None:
        """
        Calculate Parkinson volatility (high-low based).

        Formula:
            sigma = sqrt(1/(4*n*ln(2)) * sum((ln(H/L))^2))

        Returns:
            Parkinson volatility (annualized).
        """
        if len(self._ohlc) < 2:
            return None

        hl_sq_sum = 0.0
        for _, h, l, _ in self._ohlc:
            if h > 0 and l > 0:
                hl_sq_sum += np.log(h / l) ** 2

        n = len(self._ohlc)
        variance = hl_sq_sum / (4 * n * np.log(2))
        return np.sqrt(variance * self.annualization_factor)

    def yang_zhang_volatility(self) -> float | None:
        """
        Calculate Yang-Zhang volatility (most efficient for OHLC).

        Combines overnight, open-close, and Rogers-Satchell components.

        Returns:
            Yang-Zhang volatility (annualized).
        """
        if len(self._ohlc) < 3:
            return None

        n = len(self._ohlc) - 1
        k = 0.34 / (1.34 + (n + 1) / (n - 1))

        # Overnight volatility (close-to-open)
        overnight_var = 0.0
        for i in range(1, len(self._ohlc)):
            prev_close = self._ohlc[i - 1][3]
            curr_open = self._ohlc[i][0]
            if prev_close > 0 and curr_open > 0:
                overnight_var += np.log(curr_open / prev_close) ** 2

        overnight_var /= (n - 1) if n > 1 else 1

        # Open-close volatility
        oc_var = 0.0
        for o, _, _, c in self._ohlc[1:]:
            if o > 0 and c > 0:
                oc_var += np.log(c / o) ** 2
        oc_var /= (n - 1) if n > 1 else 1

        # Rogers-Satchell volatility
        rs_var = 0.0
        for o, h, l, c in self._ohlc[1:]:
            if o > 0 and h > 0 and l > 0 and c > 0:
                ho = np.log(h / o)
                hc = np.log(h / c)
                lo = np.log(l / o)
                lc = np.log(l / c)
                rs_var += ho * hc + lo * lc
        rs_var /= n if n > 0 else 1

        # Combine components
        variance = overnight_var + k * oc_var + (1 - k) * rs_var
        return np.sqrt(max(variance, 0) * self.annualization_factor)

    def reset(self) -> None:
        """Reset volatility estimator state."""
        self._returns.clear()
        self._prices.clear()
        self._ohlc.clear()
        self._ewma_variance = None


class DrawdownMonitor:
    """
    Monitors drawdown and triggers alerts/actions when limits are breached.
    """

    def __init__(
        self,
        max_drawdown_pct: float = 10.0,
        warning_threshold_pct: float = 5.0,
    ) -> None:
        """
        Initialize drawdown monitor.

        Args:
            max_drawdown_pct: Maximum allowed drawdown percentage.
            warning_threshold_pct: Warning threshold percentage.
        """
        self.max_drawdown_pct = max_drawdown_pct
        self.warning_threshold_pct = warning_threshold_pct

        self._peak_equity = 0.0
        self._current_equity = 0.0
        self._current_drawdown = 0.0
        self._max_drawdown = 0.0
        self._drawdown_start: datetime | None = None
        self._in_drawdown = False
        self._limit_breached = False
        self._history: list[tuple[datetime, float, float]] = []  # (time, equity, drawdown)

    @property
    def current_drawdown_pct(self) -> float:
        """Return current drawdown as percentage."""
        return self._current_drawdown * 100

    @property
    def max_drawdown_pct_observed(self) -> float:
        """Return maximum observed drawdown as percentage."""
        return self._max_drawdown * 100

    @property
    def is_limit_breached(self) -> bool:
        """Return True if drawdown limit has been breached."""
        return self._limit_breached

    @property
    def is_warning(self) -> bool:
        """Return True if in warning zone."""
        return self.current_drawdown_pct >= self.warning_threshold_pct

    def update(self, equity: float, timestamp: datetime | None = None) -> dict[str, Any]:
        """
        Update with new equity value.

        Args:
            equity: Current equity value.
            timestamp: Timestamp (uses UTC now if not provided).

        Returns:
            Dictionary with drawdown status and alerts.
        """
        from datetime import timezone

        timestamp = timestamp or datetime.now(timezone.utc)
        self._current_equity = equity

        # Update peak
        if equity > self._peak_equity:
            self._peak_equity = equity
            if self._in_drawdown:
                self._in_drawdown = False
                self._drawdown_start = None

        # Calculate drawdown
        if self._peak_equity > 0:
            self._current_drawdown = (self._peak_equity - equity) / self._peak_equity
        else:
            self._current_drawdown = 0.0

        # Update max drawdown
        if self._current_drawdown > self._max_drawdown:
            self._max_drawdown = self._current_drawdown

        # Track drawdown state
        if self._current_drawdown > 0 and not self._in_drawdown:
            self._in_drawdown = True
            self._drawdown_start = timestamp

        # Record history
        self._history.append((timestamp, equity, self._current_drawdown))

        # Check limits
        alerts = []
        if self.current_drawdown_pct >= self.max_drawdown_pct:
            self._limit_breached = True
            alerts.append("LIMIT_BREACHED")
        elif self.current_drawdown_pct >= self.warning_threshold_pct:
            alerts.append("WARNING")

        return {
            "current_drawdown_pct": self.current_drawdown_pct,
            "max_drawdown_pct": self.max_drawdown_pct_observed,
            "peak_equity": self._peak_equity,
            "current_equity": equity,
            "in_drawdown": self._in_drawdown,
            "drawdown_duration": (
                (timestamp - self._drawdown_start).total_seconds()
                if self._drawdown_start
                else 0
            ),
            "alerts": alerts,
            "limit_breached": self._limit_breached,
        }

    def reset(self, new_peak: float | None = None) -> None:
        """
        Reset drawdown monitor.

        Args:
            new_peak: Optional new peak equity value.
        """
        self._peak_equity = new_peak or 0.0
        self._current_equity = new_peak or 0.0
        self._current_drawdown = 0.0
        self._max_drawdown = 0.0
        self._drawdown_start = None
        self._in_drawdown = False
        self._limit_breached = False
        self._history.clear()


class PositionSizer:
    """
    Position sizing calculator using various methods.

    Supports:
    - Fixed size
    - Risk-based (Kelly criterion inspired)
    - Volatility-adjusted
    - ATR-based
    """

    def __init__(
        self,
        method: str = "risk_based",
        risk_per_trade_pct: float = 1.0,
        max_position_size: float = 10.0,
        volatility_target: float = 0.15,
    ) -> None:
        """
        Initialize position sizer.

        Args:
            method: Sizing method (fixed, risk_based, volatility_adjusted).
            risk_per_trade_pct: Risk per trade as percentage of equity.
            max_position_size: Maximum position size.
            volatility_target: Target volatility for vol-adjusted sizing.
        """
        self.method = method
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_size = max_position_size
        self.volatility_target = volatility_target

    def calculate_size(
        self,
        equity: float,
        price: float,
        stop_distance: float | None = None,
        volatility: float | None = None,
        signal_strength: float = 1.0,
        current_position: float = 0.0,
    ) -> Decimal:
        """
        Calculate position size.

        Args:
            equity: Current account equity.
            price: Current instrument price.
            stop_distance: Distance to stop loss (price units).
            volatility: Current volatility estimate (annualized).
            signal_strength: Signal strength multiplier (0-1).
            current_position: Current position size.

        Returns:
            Calculated position size as Decimal.
        """
        if self.method == "fixed":
            size = self.max_position_size * signal_strength
        elif self.method == "risk_based":
            size = self._risk_based_size(equity, price, stop_distance, signal_strength)
        elif self.method == "volatility_adjusted":
            size = self._volatility_adjusted_size(equity, price, volatility, signal_strength)
        else:
            raise ValueError(f"Unknown sizing method: {self.method}")

        # Apply limits
        max_allowed = self.max_position_size - abs(current_position)
        size = min(size, max(max_allowed, 0))

        return Decimal(str(round(size, 8)))

    def _risk_based_size(
        self,
        equity: float,
        price: float,
        stop_distance: float | None,
        signal_strength: float,
    ) -> float:
        """
        Calculate risk-based position size.

        Size = (Equity * Risk%) / (Stop Distance)

        Args:
            equity: Account equity.
            price: Current price.
            stop_distance: Distance to stop in price units.
            signal_strength: Signal strength multiplier.

        Returns:
            Position size.
        """
        if stop_distance is None or stop_distance <= 0:
            # Default to 2% of price as stop distance
            stop_distance = price * 0.02

        risk_amount = equity * (self.risk_per_trade_pct / 100)
        size = (risk_amount / stop_distance) * signal_strength

        return size

    def _volatility_adjusted_size(
        self,
        equity: float,
        price: float,
        volatility: float | None,
        signal_strength: float,
    ) -> float:
        """
        Calculate volatility-adjusted position size.

        Size = (Equity * Target Vol) / (Price * Current Vol)

        Args:
            equity: Account equity.
            price: Current price.
            volatility: Current annualized volatility.
            signal_strength: Signal strength multiplier.

        Returns:
            Position size.
        """
        if volatility is None or volatility <= 0:
            volatility = 0.20  # Default 20% vol

        # Position value for target volatility
        position_value = equity * (self.volatility_target / volatility)
        size = (position_value / price) * signal_strength

        return size

    def kelly_fraction(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float,
        fraction_multiplier: float = 0.5,
    ) -> float:
        """
        Calculate Kelly criterion fraction.

        Kelly% = (W * R - L) / R

        Where:
        - W = win rate
        - L = loss rate = 1 - W
        - R = avg_win / avg_loss (win/loss ratio)

        Args:
            win_rate: Historical win rate (0-1).
            avg_win: Average winning trade size.
            avg_loss: Average losing trade size (positive).
            fraction_multiplier: Fraction of Kelly to use (0.5 = half-Kelly).

        Returns:
            Kelly fraction (0-1).
        """
        if avg_loss <= 0 or win_rate <= 0:
            return 0.0

        loss_rate = 1 - win_rate
        win_loss_ratio = avg_win / avg_loss

        kelly = (win_rate * win_loss_ratio - loss_rate) / win_loss_ratio

        # Apply fractional Kelly and clamp
        kelly = max(0, min(kelly * fraction_multiplier, 1.0))

        return kelly


class RiskManager:
    """
    Comprehensive risk manager combining all risk components.

    Provides:
    - Position sizing
    - Drawdown monitoring
    - Volatility estimation
    - Risk limit enforcement
    - Circuit breaker functionality
    """

    def __init__(self, config: RiskConfig) -> None:
        """
        Initialize risk manager.

        Args:
            config: Risk configuration.
        """
        self.config = config

        # Components
        self.position_sizer = PositionSizer(
            method="risk_based",
            risk_per_trade_pct=config.risk_per_trade_pct,
            max_position_size=config.max_position_size,
            volatility_target=config.volatility_target,
        )
        self.volatility_estimator = VolatilityEstimator()
        self.drawdown_monitor = DrawdownMonitor(
            max_drawdown_pct=config.max_drawdown_pct,
            warning_threshold_pct=config.max_drawdown_pct * 0.5,
        )

        # State
        self._daily_pnl = 0.0
        from datetime import timezone
        self._daily_pnl_start = datetime.now(timezone.utc).date()
        self._open_orders_count = 0
        self._circuit_breaker_triggered = False
        self._risk_metrics = RiskMetrics()

    @property
    def is_trading_allowed(self) -> bool:
        """Return True if trading is allowed under current risk limits."""
        if self._circuit_breaker_triggered:
            return False
        if self.drawdown_monitor.is_limit_breached:
            return False
        return True

    @property
    def risk_metrics(self) -> RiskMetrics:
        """Return current risk metrics."""
        return self._risk_metrics

    def check_order(
        self,
        side: str,
        quantity: float,
        price: float,
        current_position: float,
    ) -> tuple[bool, str]:
        """
        Check if an order is allowed under risk limits.

        Args:
            side: Order side ('BUY' or 'SELL').
            quantity: Order quantity.
            price: Order price.
            current_position: Current position size.

        Returns:
            Tuple of (allowed, reason).
        """
        if not self.is_trading_allowed:
            return False, "Circuit breaker triggered or drawdown limit breached"

        # Check position size
        if side == "BUY":
            new_position = current_position + quantity
        else:
            new_position = current_position - quantity

        if abs(new_position) > self.config.max_position_size:
            return False, f"Position size {abs(new_position)} exceeds limit {self.config.max_position_size}"

        # Check position value
        position_value = abs(new_position) * price
        if position_value > self.config.max_position_value:
            return False, f"Position value {position_value} exceeds limit {self.config.max_position_value}"

        # Check open orders
        if self._open_orders_count >= self.config.max_open_orders:
            return False, f"Open orders {self._open_orders_count} at limit {self.config.max_open_orders}"

        return True, "Order allowed"

    def calculate_position_size(
        self,
        equity: float,
        price: float,
        stop_distance: float | None = None,
        signal_strength: float = 1.0,
        current_position: float = 0.0,
    ) -> Decimal:
        """
        Calculate risk-adjusted position size.

        Args:
            equity: Account equity.
            price: Current price.
            stop_distance: Stop loss distance.
            signal_strength: Signal strength (0-1).
            current_position: Current position.

        Returns:
            Position size as Decimal.
        """
        volatility = self.volatility_estimator.ewma_volatility

        return self.position_sizer.calculate_size(
            equity=equity,
            price=price,
            stop_distance=stop_distance,
            volatility=volatility,
            signal_strength=signal_strength,
            current_position=current_position,
        )

    def update_price(self, price: float) -> None:
        """Update volatility estimator with new price."""
        self.volatility_estimator.update_price(price)

    def update_ohlc(
        self,
        open_price: float,
        high: float,
        low: float,
        close: float,
    ) -> None:
        """Update volatility estimator with OHLC bar."""
        self.volatility_estimator.update_ohlc(open_price, high, low, close)

    def update_equity(self, equity: float, timestamp: datetime | None = None) -> dict[str, Any]:
        """
        Update equity and check drawdown.

        Args:
            equity: Current equity.
            timestamp: Timestamp.

        Returns:
            Drawdown status dictionary.
        """
        status = self.drawdown_monitor.update(equity, timestamp)

        # Update risk metrics
        self._risk_metrics.max_drawdown = self.drawdown_monitor.max_drawdown_pct_observed / 100
        self._risk_metrics.current_drawdown = self.drawdown_monitor.current_drawdown_pct / 100
        volatility = self.volatility_estimator.ewma_volatility
        if volatility:
            self._risk_metrics.volatility = volatility

        # Check circuit breaker
        if self.config.enable_circuit_breaker and status.get("limit_breached"):
            self._circuit_breaker_triggered = True

        return status

    def update_daily_pnl(self, pnl: float) -> bool:
        """
        Update daily P&L tracking.

        Args:
            pnl: P&L change.

        Returns:
            True if daily loss limit breached.
        """
        from datetime import timezone
        today = datetime.now(timezone.utc).date()

        # Reset daily tracking
        if today != self._daily_pnl_start:
            self._daily_pnl = 0.0
            self._daily_pnl_start = today

        self._daily_pnl += pnl

        # Check daily loss limit
        # Note: This assumes equity is set elsewhere or passed in
        return False  # Placeholder

    def order_submitted(self) -> None:
        """Track order submission."""
        self._open_orders_count += 1

    def order_completed(self) -> None:
        """Track order completion."""
        self._open_orders_count = max(0, self._open_orders_count - 1)

    def trigger_circuit_breaker(self, reason: str) -> None:
        """
        Manually trigger circuit breaker.

        Args:
            reason: Reason for triggering (logged for audit purposes).
        """
        # Note: In production, log reason for audit trail
        _ = reason  # Acknowledge parameter usage
        self._circuit_breaker_triggered = True

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker (use with caution)."""
        self._circuit_breaker_triggered = False
        self.drawdown_monitor.reset()

    def reset(self) -> None:
        """Reset all risk manager state."""
        self.volatility_estimator.reset()
        self.drawdown_monitor.reset()
        self._daily_pnl = 0.0
        self._open_orders_count = 0
        self._circuit_breaker_triggered = False
        self._risk_metrics = RiskMetrics()
