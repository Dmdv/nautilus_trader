"""
Circuit Breaker Implementation.

Provides risk controls and emergency stops for live trading.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Trading halted
    HALF_OPEN = "half_open"  # Testing if can resume


class CircuitBreakerTrigger(str, Enum):
    """Circuit breaker trigger types."""

    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    POSITION_LIMIT = "position_limit"
    ERROR_RATE = "error_rate"
    CONNECTIVITY = "connectivity"
    MANUAL = "manual"
    RECONCILIATION_FAILURE = "reconciliation_failure"


@dataclass
class CircuitBreakerEvent:
    """
    Circuit breaker state change event.

    Attributes:
        timestamp: Event timestamp.
        previous_state: Previous state.
        new_state: New state.
        trigger: What triggered the change.
        reason: Human-readable reason.
        details: Additional details.
    """

    timestamp: datetime
    previous_state: CircuitBreakerState
    new_state: CircuitBreakerState
    trigger: CircuitBreakerTrigger | None
    reason: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "previous_state": self.previous_state.value,
            "new_state": self.new_state.value,
            "trigger": self.trigger.value if self.trigger else None,
            "reason": self.reason,
            "details": self.details,
        }


@dataclass
class CircuitBreakerConfig:
    """
    Circuit breaker configuration.

    Attributes:
        max_daily_loss: Maximum daily loss before halt.
        max_drawdown: Maximum drawdown before halt.
        max_position_value: Maximum total position value.
        max_error_rate: Maximum error rate (errors per minute).
        cooldown_minutes: Cooldown period before auto-reset.
        auto_reset: Whether to auto-reset after cooldown.
        notify_on_trigger: Send notifications on trigger.
        notification_channels: Notification channel list.
    """

    max_daily_loss: float = 5_000.0
    max_drawdown: float = 0.10  # 10%
    max_position_value: float = 100_000.0
    max_error_rate: float = 10.0  # errors per minute
    cooldown_minutes: int = 60
    auto_reset: bool = False
    notify_on_trigger: bool = True
    notification_channels: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "max_daily_loss": self.max_daily_loss,
            "max_drawdown": self.max_drawdown,
            "max_position_value": self.max_position_value,
            "max_error_rate": self.max_error_rate,
            "cooldown_minutes": self.cooldown_minutes,
            "auto_reset": self.auto_reset,
            "notify_on_trigger": self.notify_on_trigger,
            "notification_channels": self.notification_channels,
        }


class CircuitBreaker:
    """
    Circuit breaker for risk management.

    Monitors trading metrics and halts trading when
    risk thresholds are exceeded.
    """

    def __init__(
        self,
        config: CircuitBreakerConfig | None = None,
    ) -> None:
        """
        Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration.
        """
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState.CLOSED
        self._events: list[CircuitBreakerEvent] = []
        self._triggered_at: datetime | None = None
        self._daily_pnl: float = 0.0
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._position_value: float = 0.0
        self._error_count: int = 0
        self._error_window_start: datetime | None = None
        self._on_trigger_callbacks: list[Callable[[CircuitBreakerEvent], None]] = []

    @property
    def state(self) -> CircuitBreakerState:
        """Get current state."""
        return self._state

    @property
    def is_trading_allowed(self) -> bool:
        """Check if trading is allowed."""
        return self._state == CircuitBreakerState.CLOSED

    @property
    def events(self) -> list[CircuitBreakerEvent]:
        """Get state change events."""
        return self._events.copy()

    def on_trigger(
        self,
        callback: Callable[[CircuitBreakerEvent], None],
    ) -> None:
        """
        Register callback for trigger events.

        Args:
            callback: Function to call when triggered.
        """
        self._on_trigger_callbacks.append(callback)

    def update_pnl(self, daily_pnl: float) -> None:
        """
        Update daily P&L.

        Args:
            daily_pnl: Current daily P&L.
        """
        self._daily_pnl = daily_pnl
        self._check_daily_loss()

    def update_equity(self, equity: float) -> None:
        """
        Update equity for drawdown calculation.

        Args:
            equity: Current equity value.
        """
        self._current_equity = equity
        if equity > self._peak_equity:
            self._peak_equity = equity
        self._check_drawdown()

    def update_position_value(self, value: float) -> None:
        """
        Update total position value.

        Args:
            value: Total position value.
        """
        self._position_value = value
        self._check_position_limit()

    def record_error(self) -> None:
        """Record an error occurrence."""
        now = datetime.now(timezone.utc)

        # Reset window if expired
        if self._error_window_start is None:
            self._error_window_start = now
            self._error_count = 0

        window_elapsed = (now - self._error_window_start).total_seconds()
        if window_elapsed > 60:  # 1 minute window
            self._error_window_start = now
            self._error_count = 0

        self._error_count += 1
        self._check_error_rate()

    def reset(self, manual: bool = False) -> None:
        """
        Reset circuit breaker to closed state.

        Args:
            manual: Whether this is a manual reset.
        """
        if self._state != CircuitBreakerState.CLOSED:
            event = CircuitBreakerEvent(
                timestamp=datetime.now(timezone.utc),
                previous_state=self._state,
                new_state=CircuitBreakerState.CLOSED,
                trigger=CircuitBreakerTrigger.MANUAL if manual else None,
                reason="Manual reset" if manual else "Auto reset after cooldown",
            )
            self._state = CircuitBreakerState.CLOSED
            self._triggered_at = None
            self._events.append(event)

    def trigger(
        self,
        trigger_type: CircuitBreakerTrigger,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Manually trigger circuit breaker.

        Args:
            trigger_type: Type of trigger.
            reason: Reason for triggering.
            details: Additional details.
        """
        self._trigger_internal(trigger_type, reason, details or {})

    def check_cooldown(self) -> bool:
        """
        Check if cooldown has elapsed.

        Returns:
            True if cooldown elapsed and can reset.
        """
        if self._triggered_at is None:
            return False

        elapsed = (datetime.now(timezone.utc) - self._triggered_at).total_seconds()
        cooldown_seconds = self.config.cooldown_minutes * 60
        return elapsed >= cooldown_seconds

    def try_auto_reset(self) -> bool:
        """
        Attempt auto-reset if cooldown elapsed.

        Returns:
            True if reset was performed.
        """
        if not self.config.auto_reset:
            return False

        if self._state == CircuitBreakerState.OPEN and self.check_cooldown():
            self.reset(manual=False)
            return True

        return False

    def get_status(self) -> dict[str, Any]:
        """Get current status."""
        return {
            "state": self._state.value,
            "is_trading_allowed": self.is_trading_allowed,
            "daily_pnl": self._daily_pnl,
            "current_drawdown": self._calculate_drawdown(),
            "position_value": self._position_value,
            "error_count": self._error_count,
            "triggered_at": self._triggered_at.isoformat() if self._triggered_at else None,
            "cooldown_remaining": self._get_cooldown_remaining(),
        }

    def _check_daily_loss(self) -> None:
        """Check if daily loss limit exceeded."""
        if self._daily_pnl < -self.config.max_daily_loss:
            self._trigger_internal(
                CircuitBreakerTrigger.DAILY_LOSS_LIMIT,
                f"Daily loss {self._daily_pnl:.2f} exceeds limit {-self.config.max_daily_loss:.2f}",
                {"daily_pnl": self._daily_pnl, "limit": self.config.max_daily_loss},
            )

    def _check_drawdown(self) -> None:
        """Check if drawdown limit exceeded."""
        drawdown = self._calculate_drawdown()
        if drawdown > self.config.max_drawdown:
            self._trigger_internal(
                CircuitBreakerTrigger.DRAWDOWN_LIMIT,
                f"Drawdown {drawdown:.2%} exceeds limit {self.config.max_drawdown:.2%}",
                {"drawdown": drawdown, "limit": self.config.max_drawdown},
            )

    def _check_position_limit(self) -> None:
        """Check if position limit exceeded."""
        if self._position_value > self.config.max_position_value:
            self._trigger_internal(
                CircuitBreakerTrigger.POSITION_LIMIT,
                f"Position value {self._position_value:.2f} exceeds limit {self.config.max_position_value:.2f}",
                {"position_value": self._position_value, "limit": self.config.max_position_value},
            )

    def _check_error_rate(self) -> None:
        """Check if error rate exceeded."""
        if self._error_count > self.config.max_error_rate:
            self._trigger_internal(
                CircuitBreakerTrigger.ERROR_RATE,
                f"Error rate {self._error_count}/min exceeds limit {self.config.max_error_rate}",
                {"error_count": self._error_count, "limit": self.config.max_error_rate},
            )

    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown."""
        if self._peak_equity <= 0:
            return 0.0
        return (self._peak_equity - self._current_equity) / self._peak_equity

    def _get_cooldown_remaining(self) -> float:
        """Get remaining cooldown time in seconds."""
        if self._triggered_at is None:
            return 0.0

        elapsed = (datetime.now(timezone.utc) - self._triggered_at).total_seconds()
        cooldown_seconds = self.config.cooldown_minutes * 60
        remaining = cooldown_seconds - elapsed
        return max(0.0, remaining)

    def _trigger_internal(
        self,
        trigger_type: CircuitBreakerTrigger,
        reason: str,
        details: dict[str, Any],
    ) -> None:
        """Internal trigger implementation."""
        if self._state == CircuitBreakerState.OPEN:
            return  # Already triggered

        event = CircuitBreakerEvent(
            timestamp=datetime.now(timezone.utc),
            previous_state=self._state,
            new_state=CircuitBreakerState.OPEN,
            trigger=trigger_type,
            reason=reason,
            details=details,
        )

        self._state = CircuitBreakerState.OPEN
        self._triggered_at = datetime.now(timezone.utc)
        self._events.append(event)

        # Notify callbacks
        import logging
        logger = logging.getLogger(__name__)
        for callback in self._on_trigger_callbacks:
            try:
                callback(event)
            except Exception as e:
                # Log but don't let callback errors affect circuit breaker
                logger.error(f"Circuit breaker callback failed: {e}")

    def reset_daily(self) -> None:
        """Reset daily counters."""
        self._daily_pnl = 0.0
        self._error_count = 0
        self._error_window_start = None
