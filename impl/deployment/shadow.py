"""
Shadow Mode Implementation.

Provides shadow trading functionality where orders are tracked
and compared against live market execution without actual trades.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np


@dataclass
class ShadowFill:
    """
    Simulated fill for shadow trading.

    Attributes:
        fill_id: Unique fill identifier.
        order_id: Associated order ID.
        instrument_id: Instrument identifier.
        side: Trade side (BUY/SELL).
        quantity: Fill quantity.
        price: Fill price.
        timestamp: Fill timestamp.
        market_price_at_signal: Market price when signal generated.
        actual_market_price: Actual market price at fill time.
        slippage: Price slippage from signal.
    """

    fill_id: str
    order_id: str
    instrument_id: str
    side: str
    quantity: float
    price: float
    timestamp: datetime
    market_price_at_signal: float
    actual_market_price: float
    slippage: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "timestamp": self.timestamp.isoformat(),
            "market_price_at_signal": self.market_price_at_signal,
            "actual_market_price": self.actual_market_price,
            "slippage": self.slippage,
        }


@dataclass
class ShadowPosition:
    """
    Shadow position tracking.

    Attributes:
        instrument_id: Instrument identifier.
        quantity: Position quantity (+ long, - short).
        avg_entry_price: Average entry price.
        unrealized_pnl: Unrealized P&L.
        realized_pnl: Realized P&L.
    """

    instrument_id: str
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def update_unrealized_pnl(self, current_price: float) -> None:
        """Update unrealized P&L based on current price."""
        if self.quantity != 0:
            self.unrealized_pnl = (current_price - self.avg_entry_price) * self.quantity

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "instrument_id": self.instrument_id,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
        }


class ShadowOrderTracker:
    """
    Tracks shadow orders and positions.

    Simulates order execution and tracks hypothetical P&L
    without submitting actual orders.
    """

    def __init__(
        self,
        slippage_bps: float = 5.0,
        fill_probability: float = 1.0,
    ) -> None:
        """
        Initialize shadow tracker.

        Args:
            slippage_bps: Assumed slippage in basis points.
            fill_probability: Probability of fill (for limit orders).
        """
        self.slippage_bps = slippage_bps
        self.fill_probability = fill_probability
        self._fills: list[ShadowFill] = []
        self._positions: dict[str, ShadowPosition] = {}
        self._order_counter = 0
        self._fill_counter = 0

    @property
    def fills(self) -> list[ShadowFill]:
        """Get all shadow fills."""
        return self._fills.copy()

    @property
    def positions(self) -> dict[str, ShadowPosition]:
        """Get current shadow positions."""
        return {k: v for k, v in self._positions.items()}

    def track_order(
        self,
        instrument_id: str,
        side: str,
        quantity: float,
        market_price: float,
        signal_price: float | None = None,
        timestamp: datetime | None = None,
    ) -> ShadowFill | None:
        """
        Track an order and simulate fill.

        Args:
            instrument_id: Instrument identifier.
            side: Order side (BUY/SELL).
            quantity: Order quantity.
            market_price: Current market price.
            signal_price: Price when signal was generated.
            timestamp: Order timestamp.

        Returns:
            ShadowFill if order is filled, None otherwise.
        """
        self._order_counter += 1
        timestamp = timestamp or datetime.now(timezone.utc)
        signal_price = signal_price or market_price

        # Check fill probability
        if np.random.random() > self.fill_probability:
            return None

        # Calculate fill price with slippage
        slippage_factor = self.slippage_bps / 10000.0
        if side == "BUY":
            fill_price = market_price * (1 + slippage_factor)
        else:
            fill_price = market_price * (1 - slippage_factor)

        # Calculate slippage from signal
        slippage = (fill_price - signal_price) / signal_price
        if side == "SELL":
            slippage = -slippage

        self._fill_counter += 1
        fill = ShadowFill(
            fill_id=f"SHADOW-FILL-{self._fill_counter:06d}",
            order_id=f"SHADOW-ORDER-{self._order_counter:06d}",
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            price=fill_price,
            timestamp=timestamp,
            market_price_at_signal=signal_price,
            actual_market_price=market_price,
            slippage=slippage,
        )

        self._fills.append(fill)
        self._update_position(fill)
        return fill

    def _update_position(self, fill: ShadowFill) -> None:
        """Update position from fill."""
        if fill.instrument_id not in self._positions:
            self._positions[fill.instrument_id] = ShadowPosition(
                instrument_id=fill.instrument_id
            )

        pos = self._positions[fill.instrument_id]
        fill_qty = fill.quantity if fill.side == "BUY" else -fill.quantity

        if pos.quantity == 0:
            # New position
            pos.quantity = fill_qty
            pos.avg_entry_price = fill.price
        elif (pos.quantity > 0 and fill_qty > 0) or (pos.quantity < 0 and fill_qty < 0):
            # Adding to position
            total_cost = pos.avg_entry_price * abs(pos.quantity) + fill.price * abs(fill_qty)
            pos.quantity += fill_qty
            if pos.quantity != 0:
                pos.avg_entry_price = total_cost / abs(pos.quantity)
        else:
            # Reducing or reversing position
            if abs(fill_qty) <= abs(pos.quantity):
                # Reducing position - realize P&L
                realized = (fill.price - pos.avg_entry_price) * abs(fill_qty)
                if pos.quantity < 0:
                    realized = -realized
                pos.realized_pnl += realized
                pos.quantity += fill_qty
            else:
                # Reversing position
                close_qty = abs(pos.quantity)
                realized = (fill.price - pos.avg_entry_price) * close_qty
                if pos.quantity < 0:
                    realized = -realized
                pos.realized_pnl += realized

                # New position in opposite direction
                remaining = abs(fill_qty) - close_qty
                pos.quantity = remaining if fill_qty > 0 else -remaining
                pos.avg_entry_price = fill.price

    def get_total_pnl(self) -> float:
        """Get total P&L across all positions."""
        return sum(p.realized_pnl + p.unrealized_pnl for p in self._positions.values())

    def update_all_unrealized_pnl(
        self,
        prices: dict[str, float],
    ) -> None:
        """Update unrealized P&L for all positions."""
        for instrument_id, pos in self._positions.items():
            if instrument_id in prices:
                pos.update_unrealized_pnl(prices[instrument_id])

    def clear(self) -> None:
        """Clear all tracking data."""
        self._fills.clear()
        self._positions.clear()
        self._order_counter = 0
        self._fill_counter = 0


@dataclass
class ShadowMetrics:
    """
    Metrics from shadow trading validation.

    Attributes:
        runtime_hours: Total runtime in hours.
        total_orders: Total orders tracked.
        total_fills: Total fills simulated.
        fill_rate: Fill rate percentage.
        total_pnl: Total P&L (realized + unrealized).
        realized_pnl: Realized P&L.
        sharpe_ratio: Sharpe ratio of returns.
        max_drawdown: Maximum drawdown.
        tracking_error: Tracking error vs market.
        correlation: Correlation with market returns.
        is_valid: Whether shadow run passes validation.
    """

    runtime_hours: float
    total_orders: int
    total_fills: int
    fill_rate: float
    total_pnl: float
    realized_pnl: float
    sharpe_ratio: float
    max_drawdown: float
    tracking_error: float
    correlation: float
    is_valid: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "runtime_hours": self.runtime_hours,
            "total_orders": self.total_orders,
            "total_fills": self.total_fills,
            "fill_rate": self.fill_rate,
            "total_pnl": self.total_pnl,
            "realized_pnl": self.realized_pnl,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "tracking_error": self.tracking_error,
            "correlation": self.correlation,
            "is_valid": self.is_valid,
        }


class ShadowValidator:
    """
    Validates shadow trading results for mode promotion.

    Checks that shadow trading produces acceptable results
    compared to live market conditions.
    """

    def __init__(
        self,
        min_runtime_hours: float = 24.0,
        max_tracking_error: float = 0.01,
        min_correlation: float = 0.95,
        min_sharpe: float = 0.0,
    ) -> None:
        """
        Initialize validator.

        Args:
            min_runtime_hours: Minimum required runtime.
            max_tracking_error: Maximum acceptable tracking error.
            min_correlation: Minimum correlation with market.
            min_sharpe: Minimum Sharpe ratio.
        """
        self.min_runtime_hours = min_runtime_hours
        self.max_tracking_error = max_tracking_error
        self.min_correlation = min_correlation
        self.min_sharpe = min_sharpe

    def validate(
        self,
        tracker: ShadowOrderTracker,
        start_time: datetime,
        end_time: datetime,
        market_returns: list[float] | None = None,
        strategy_returns: list[float] | None = None,
    ) -> ShadowMetrics:
        """
        Validate shadow trading results.

        Args:
            tracker: Shadow order tracker.
            start_time: Trading start time.
            end_time: Trading end time.
            market_returns: Market return series (optional).
            strategy_returns: Strategy return series (optional).

        Returns:
            ShadowMetrics with validation results.
        """
        runtime = (end_time - start_time).total_seconds() / 3600.0
        fills = tracker.fills

        # Basic metrics
        total_orders = tracker._order_counter
        total_fills = len(fills)
        fill_rate = total_fills / total_orders if total_orders > 0 else 0.0

        # P&L metrics
        total_pnl = tracker.get_total_pnl()
        realized_pnl = sum(p.realized_pnl for p in tracker.positions.values())

        # Calculate Sharpe and drawdown from strategy returns
        sharpe_ratio = 0.0
        max_drawdown = 0.0
        if strategy_returns:
            returns_arr = np.array(strategy_returns)
            if len(returns_arr) > 1:
                std = np.std(returns_arr)
                if std > 1e-10:
                    sharpe_ratio = float(np.mean(returns_arr) / std * np.sqrt(252))

                # Calculate drawdown
                cumulative = np.cumsum(returns_arr)
                running_max = np.maximum.accumulate(cumulative)
                drawdown = running_max - cumulative
                max_drawdown = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        # Calculate tracking error and correlation
        tracking_error = 0.0
        correlation = 1.0
        if market_returns and strategy_returns:
            market_arr = np.array(market_returns)
            strat_arr = np.array(strategy_returns)
            min_len = min(len(market_arr), len(strat_arr))
            if min_len > 1:
                market_arr = market_arr[:min_len]
                strat_arr = strat_arr[:min_len]
                diff = strat_arr - market_arr
                tracking_error = float(np.std(diff))
                if np.std(market_arr) > 1e-10 and np.std(strat_arr) > 1e-10:
                    correlation = float(np.corrcoef(market_arr, strat_arr)[0, 1])

        # Validate
        is_valid = (
            runtime >= self.min_runtime_hours
            and tracking_error <= self.max_tracking_error
            and correlation >= self.min_correlation
            and sharpe_ratio >= self.min_sharpe
        )

        return ShadowMetrics(
            runtime_hours=runtime,
            total_orders=total_orders,
            total_fills=total_fills,
            fill_rate=fill_rate,
            total_pnl=total_pnl,
            realized_pnl=realized_pnl,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            tracking_error=tracking_error,
            correlation=correlation,
            is_valid=is_valid,
        )
