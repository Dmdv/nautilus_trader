"""
Dry-Run Mode Implementation.

Provides order tracking and validation for dry-run mode
where orders are logged but not submitted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import numpy as np


@dataclass
class DryRunOrder:
    """
    Recorded dry-run order.

    Attributes:
        order_id: Unique order identifier.
        instrument_id: Instrument being traded.
        side: Order side (BUY/SELL).
        quantity: Order quantity.
        order_type: Order type (MARKET/LIMIT).
        price: Limit price (None for market).
        signal_time: Time signal was generated.
        market_price: Market price at signal time.
        hypothetical_fill_price: Simulated fill price.
        slippage: Difference between signal and fill price.
    """

    order_id: str
    instrument_id: str
    side: str
    quantity: float
    order_type: str
    price: float | None
    signal_time: datetime
    market_price: float
    hypothetical_fill_price: float | None = None
    slippage: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "instrument_id": self.instrument_id,
            "side": self.side,
            "quantity": self.quantity,
            "order_type": self.order_type,
            "price": self.price,
            "signal_time": self.signal_time.isoformat(),
            "market_price": self.market_price,
            "hypothetical_fill_price": self.hypothetical_fill_price,
            "slippage": self.slippage,
        }


class DryRunOrderTracker:
    """
    Tracks orders in dry-run mode.

    Logs all order intentions and calculates hypothetical fills
    without actually submitting orders to the exchange.
    """

    def __init__(
        self,
        slippage_model: str = "fixed",
        fixed_slippage_bps: float = 5.0,
    ) -> None:
        """
        Initialize order tracker.

        Args:
            slippage_model: Slippage model type ('fixed', 'percentage', 'volume').
            fixed_slippage_bps: Fixed slippage in basis points.
        """
        self.slippage_model = slippage_model
        self.fixed_slippage_bps = fixed_slippage_bps
        self._orders: list[DryRunOrder] = []
        self._order_counter = 0

    @property
    def orders(self) -> list[DryRunOrder]:
        """Get all tracked orders."""
        return self._orders.copy()

    @property
    def order_count(self) -> int:
        """Get total order count."""
        return len(self._orders)

    def track_order(
        self,
        instrument_id: str,
        side: str,
        quantity: float,
        order_type: str,
        price: float | None,
        market_price: float,
        signal_time: datetime | None = None,
    ) -> DryRunOrder:
        """
        Track a new order intention.

        Args:
            instrument_id: Instrument identifier.
            side: Order side (BUY/SELL).
            quantity: Order quantity.
            order_type: Order type (MARKET/LIMIT).
            price: Limit price (None for market orders).
            market_price: Current market price.
            signal_time: Signal generation time.

        Returns:
            Tracked order with hypothetical fill.

        Raises:
            ValueError: If quantity <= 0 or side not in (BUY, SELL).
        """
        # Input validation
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {quantity}")
        if side not in ("BUY", "SELL"):
            raise ValueError(f"Side must be BUY or SELL, got {side}")

        self._order_counter += 1
        signal_time = signal_time or datetime.now(timezone.utc)

        # Calculate hypothetical fill price
        fill_price = self._calculate_fill_price(
            side=side,
            order_type=order_type,
            limit_price=price,
            market_price=market_price,
        )

        # Calculate slippage
        slippage = None
        if fill_price is not None:
            if side == "BUY":
                slippage = (fill_price - market_price) / market_price
            else:
                slippage = (market_price - fill_price) / market_price

        order = DryRunOrder(
            order_id=f"DRY-{self._order_counter:06d}",
            instrument_id=instrument_id,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            signal_time=signal_time,
            market_price=market_price,
            hypothetical_fill_price=fill_price,
            slippage=slippage,
        )

        self._orders.append(order)
        return order

    def _calculate_fill_price(
        self,
        side: str,
        order_type: str,
        limit_price: float | None,
        market_price: float,
    ) -> float | None:
        """Calculate hypothetical fill price."""
        if order_type == "LIMIT":
            # Limit orders fill at limit price or better
            if side == "BUY" and limit_price is not None:
                return min(limit_price, market_price)
            elif side == "SELL" and limit_price is not None:
                return max(limit_price, market_price)
            return limit_price

        # Market order with slippage
        slippage_factor = self.fixed_slippage_bps / 10000.0

        if side == "BUY":
            return market_price * (1 + slippage_factor)
        else:
            return market_price * (1 - slippage_factor)

    def get_orders_by_instrument(
        self,
        instrument_id: str,
    ) -> list[DryRunOrder]:
        """Get orders for specific instrument."""
        return [o for o in self._orders if o.instrument_id == instrument_id]

    def get_orders_in_range(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> list[DryRunOrder]:
        """Get orders within time range."""
        return [
            o for o in self._orders
            if start_time <= o.signal_time <= end_time
        ]

    def clear(self) -> None:
        """Clear all tracked orders."""
        self._orders.clear()
        self._order_counter = 0


@dataclass
class DryRunMetrics:
    """
    Metrics from dry-run validation.

    Attributes:
        total_signals: Total signal count.
        buy_signals: Buy signal count.
        sell_signals: Sell signal count.
        avg_slippage: Average slippage.
        max_slippage: Maximum slippage.
        slippage_std: Slippage standard deviation.
        signals_within_tolerance: Signals within slippage tolerance.
        pass_rate: Percentage of signals within tolerance.
        is_valid: Whether dry-run passes validation.
    """

    total_signals: int
    buy_signals: int
    sell_signals: int
    avg_slippage: float
    max_slippage: float
    slippage_std: float
    signals_within_tolerance: int
    pass_rate: float
    is_valid: bool

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_signals": self.total_signals,
            "buy_signals": self.buy_signals,
            "sell_signals": self.sell_signals,
            "avg_slippage": self.avg_slippage,
            "max_slippage": self.max_slippage,
            "slippage_std": self.slippage_std,
            "signals_within_tolerance": self.signals_within_tolerance,
            "pass_rate": self.pass_rate,
            "is_valid": self.is_valid,
        }


class DryRunValidator:
    """
    Validates dry-run results for mode promotion.

    Checks that signals are generated correctly and
    slippage is within acceptable bounds.
    """

    def __init__(
        self,
        min_signals: int = 100,
        max_slippage_tolerance: float = 0.005,
        min_pass_rate: float = 0.95,
    ) -> None:
        """
        Initialize validator.

        Args:
            min_signals: Minimum signals required.
            max_slippage_tolerance: Maximum acceptable slippage.
            min_pass_rate: Minimum pass rate for promotion.
        """
        self.min_signals = min_signals
        self.max_slippage_tolerance = max_slippage_tolerance
        self.min_pass_rate = min_pass_rate

    def validate(
        self,
        tracker: DryRunOrderTracker,
    ) -> DryRunMetrics:
        """
        Validate dry-run results.

        Args:
            tracker: Order tracker with recorded orders.

        Returns:
            DryRunMetrics with validation results.
        """
        orders = tracker.orders

        if not orders:
            return DryRunMetrics(
                total_signals=0,
                buy_signals=0,
                sell_signals=0,
                avg_slippage=0.0,
                max_slippage=0.0,
                slippage_std=0.0,
                signals_within_tolerance=0,
                pass_rate=0.0,
                is_valid=False,
            )

        # Count signals
        buy_signals = sum(1 for o in orders if o.side == "BUY")
        sell_signals = sum(1 for o in orders if o.side == "SELL")

        # Calculate slippage statistics
        slippages = [
            abs(o.slippage) for o in orders
            if o.slippage is not None
        ]

        if slippages:
            avg_slippage = float(np.mean(slippages))
            max_slippage = float(np.max(slippages))
            slippage_std = float(np.std(slippages))
        else:
            avg_slippage = 0.0
            max_slippage = 0.0
            slippage_std = 0.0

        # Count within tolerance
        signals_within_tolerance = sum(
            1 for s in slippages
            if s <= self.max_slippage_tolerance
        )

        pass_rate = signals_within_tolerance / len(orders) if orders else 0.0

        # Validate
        is_valid = (
            len(orders) >= self.min_signals
            and pass_rate >= self.min_pass_rate
        )

        return DryRunMetrics(
            total_signals=len(orders),
            buy_signals=buy_signals,
            sell_signals=sell_signals,
            avg_slippage=avg_slippage,
            max_slippage=max_slippage,
            slippage_std=slippage_std,
            signals_within_tolerance=signals_within_tolerance,
            pass_rate=pass_rate,
            is_valid=is_valid,
        )
