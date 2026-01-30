"""
Base Strategy Module.

Provides a foundation class with common functionality for all trading strategies,
including position tracking, P&L calculation, and order management utilities.
"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.datetime import unix_nanos_to_dt
from nautilus_trader.model.data import Bar, QuoteTick, TradeTick
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.events import (
    OrderAccepted,
    OrderCanceled,
    OrderFilled,
    OrderRejected,
    PositionChanged,
    PositionClosed,
    PositionOpened,
)
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Price  # noqa: F401 - used by subclasses
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy


class BaseStrategyConfig(StrategyConfig, frozen=True):
    """
    Base configuration for all trading strategies.

    Attributes:
        instrument_id: The instrument identifier string.
        bar_type: The bar type string for data subscription.
        trade_size: Default trade size as string (converted to Decimal).
        max_position_size: Maximum allowed position size.
        risk_per_trade: Risk per trade as fraction of account (0.01 = 1%).
        enable_logging: Whether to enable detailed logging.
    """

    instrument_id: str
    bar_type: str
    trade_size: str = "0.01"
    max_position_size: float = 10.0
    risk_per_trade: float = 0.02
    enable_logging: bool = True


@dataclass
class TradeRecord:
    """Record of a completed trade for P&L tracking."""

    entry_time: datetime
    exit_time: datetime
    side: OrderSide
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    fees: float = 0.0

    @property
    def duration_seconds(self) -> float:
        """Return trade duration in seconds."""
        return (self.exit_time - self.entry_time).total_seconds()


@dataclass
class PositionState:
    """Current position state tracking."""

    instrument_id: InstrumentId
    side: OrderSide | None = None
    quantity: float = 0.0
    entry_price: float = 0.0
    entry_time: datetime | None = None
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    @property
    def is_flat(self) -> bool:
        """Return True if no position."""
        return self.quantity == 0.0

    @property
    def is_long(self) -> bool:
        """Return True if long position."""
        return self.side == OrderSide.BUY and self.quantity > 0

    @property
    def is_short(self) -> bool:
        """Return True if short position."""
        return self.side == OrderSide.SELL and self.quantity > 0

    def update_unrealized_pnl(self, current_price: float) -> None:
        """Update unrealized P&L based on current price."""
        self.current_price = current_price
        if self.is_flat:
            self.unrealized_pnl = 0.0
        elif self.is_long:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        elif self.is_short:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity


@dataclass
class StrategyMetrics:
    """Strategy performance metrics."""

    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    peak_equity: float = 0.0
    current_drawdown: float = 0.0
    total_fees: float = 0.0
    trades: list[TradeRecord] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        """Return win rate as fraction."""
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    @property
    def avg_win(self) -> float:
        """Return average winning trade P&L."""
        wins = [t.pnl for t in self.trades if t.pnl > 0]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        """Return average losing trade P&L (negative)."""
        losses = [t.pnl for t in self.trades if t.pnl < 0]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def profit_factor(self) -> float:
        """Return profit factor (gross profit / gross loss)."""
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def expectancy(self) -> float:
        """Return expectancy (expected value per trade)."""
        if self.total_trades == 0:
            return 0.0
        return self.total_pnl / self.total_trades

    def update_equity(self, equity: float) -> None:
        """Update drawdown tracking with current equity."""
        if equity > self.peak_equity:
            self.peak_equity = equity
        self.current_drawdown = (self.peak_equity - equity) / self.peak_equity if self.peak_equity > 0 else 0.0
        self.max_drawdown = max(self.max_drawdown, self.current_drawdown)


class BaseStrategy(Strategy):
    """
    Base strategy class with common functionality.

    Provides:
    - Position tracking and P&L calculation
    - Order management utilities
    - State persistence (save/load)
    - Performance metrics
    - Logging helpers

    Subclasses must implement:
    - on_bar: Bar data handler
    - _check_signal: Signal generation logic
    """

    def __init__(self, config: BaseStrategyConfig) -> None:
        """
        Initialize the base strategy.

        Args:
            config: Strategy configuration.
        """
        super().__init__(config)

        # Parse identifiers
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.trade_size = Decimal(config.trade_size)
        self.max_position_size = config.max_position_size

        # Internal state
        self._position_state = PositionState(instrument_id=self.instrument_id)
        self._metrics = StrategyMetrics()
        self._pending_orders: dict[str, MarketOrder] = {}
        self._is_active = False

    @property
    def position_state(self) -> PositionState:
        """Return current position state."""
        return self._position_state

    @property
    def metrics(self) -> StrategyMetrics:
        """Return strategy metrics."""
        return self._metrics

    @property
    def instrument(self):
        """Return the instrument from cache."""
        return self.cache.instrument(self.instrument_id)

    def on_start(self) -> None:
        """Called when strategy starts."""
        self._is_active = True
        self._subscribe_data()
        self.log.info(f"Strategy {self.id} started for {self.instrument_id}")

    def _subscribe_data(self) -> None:
        """Subscribe to market data. Override in subclasses for additional subscriptions."""
        from nautilus_trader.model.data import BarType

        bar_type = BarType.from_str(self.config.bar_type)
        self.subscribe_bars(bar_type)

    @abstractmethod
    def on_bar(self, bar: Bar) -> None:
        """
        Handle bar data update.

        Must be implemented by subclasses.

        Args:
            bar: The bar data.
        """
        pass

    def on_quote_tick(self, _tick: QuoteTick) -> None:
        """
        Handle quote tick update.

        Override in subclasses for quote-based strategies.

        Args:
            _tick: The quote tick data.
        """
        pass

    def on_trade_tick(self, _tick: TradeTick) -> None:
        """
        Handle trade tick update.

        Override in subclasses for tick-based strategies.

        Args:
            _tick: The trade tick data.
        """
        pass

    @abstractmethod
    def _check_signal(self) -> None:
        """
        Check for trading signals.

        Must be implemented by subclasses.
        """
        pass

    # Order Management Methods

    def submit_market_order(
        self,
        side: OrderSide,
        quantity: Decimal | None = None,
        time_in_force: TimeInForce = TimeInForce.IOC,
        reduce_only: bool = False,
    ) -> None:
        """
        Submit a market order.

        Args:
            side: Order side (BUY or SELL).
            quantity: Order quantity (uses default trade_size if None).
            time_in_force: Time in force (default IOC).
            reduce_only: Whether order should only reduce position.
        """
        if quantity is None:
            quantity = self.trade_size

        instrument = self.instrument
        if instrument is None:
            self.log.error("Cannot submit market order - instrument not found in cache")
            return

        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=side,
            quantity=instrument.make_qty(quantity),
            time_in_force=time_in_force,
            reduce_only=reduce_only,
        )
        self._pending_orders[order.client_order_id.value] = order
        self.submit_order(order)

        if self.config.enable_logging:
            self.log.info(f"Submitted market {side.name} order: qty={quantity}")

    def submit_limit_order(
        self,
        side: OrderSide,
        price: float,
        quantity: Decimal | None = None,
        time_in_force: TimeInForce = TimeInForce.GTC,
        post_only: bool = False,
        reduce_only: bool = False,
    ) -> None:
        """
        Submit a limit order.

        Args:
            side: Order side (BUY or SELL).
            price: Limit price.
            quantity: Order quantity (uses default trade_size if None).
            time_in_force: Time in force (default GTC).
            post_only: Whether order should be post-only.
            reduce_only: Whether order should only reduce position.
        """
        if quantity is None:
            quantity = self.trade_size

        instrument = self.instrument
        if instrument is None:
            self.log.error("Cannot submit limit order - instrument not found in cache")
            return

        order = self.order_factory.limit(
            instrument_id=self.instrument_id,
            order_side=side,
            quantity=instrument.make_qty(quantity),
            price=instrument.make_price(price),
            time_in_force=time_in_force,
            post_only=post_only,
            reduce_only=reduce_only,
        )
        self._pending_orders[order.client_order_id.value] = order
        self.submit_order(order)

        if self.config.enable_logging:
            self.log.info(f"Submitted limit {side.name} order: price={price}, qty={quantity}")

    def cancel_all_open_orders(self) -> None:
        """Cancel all open orders for this instrument."""
        self.cancel_all_orders(self.instrument_id)
        self._pending_orders.clear()

        if self.config.enable_logging:
            self.log.info("Cancelled all open orders")

    def close_position(self) -> None:
        """Close any open position."""
        self.close_all_positions(self.instrument_id)

        if self.config.enable_logging:
            self.log.info("Closed all positions")

    def flatten(self) -> None:
        """Cancel all orders and close all positions."""
        self.cancel_all_open_orders()
        self.close_position()

    # Order Event Handlers

    def on_order_accepted(self, event: OrderAccepted) -> None:
        """Handle order accepted event."""
        if self.config.enable_logging:
            self.log.debug(f"Order accepted: {event.client_order_id}")

    def on_order_rejected(self, event: OrderRejected) -> None:
        """Handle order rejected event."""
        order_id = event.client_order_id.value
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]

        self.log.error(f"Order rejected: {event.reason}")

    def on_order_filled(self, event: OrderFilled) -> None:
        """Handle order filled event."""
        order_id = event.client_order_id.value
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]

        # Update metrics with fees
        if event.commission:
            self._metrics.total_fees += event.commission.as_double()

        if self.config.enable_logging:
            self.log.info(
                f"Order filled: side={event.order_side.name}, "
                f"qty={event.last_qty}, price={event.last_px}"
            )

    def on_order_canceled(self, event: OrderCanceled) -> None:
        """Handle order canceled event."""
        order_id = event.client_order_id.value
        if order_id in self._pending_orders:
            del self._pending_orders[order_id]

        if self.config.enable_logging:
            self.log.debug(f"Order canceled: {event.client_order_id}")

    # Position Event Handlers

    def on_position_opened(self, event: PositionOpened) -> None:
        """Handle position opened event."""
        position = event.position
        self._position_state.side = position.side
        self._position_state.quantity = position.quantity.as_double()
        self._position_state.entry_price = position.avg_px_open
        self._position_state.entry_time = unix_nanos_to_dt(position.ts_opened)

        if self.config.enable_logging:
            self.log.info(
                f"Position opened: side={position.side.name}, "
                f"qty={position.quantity}, entry_price={position.avg_px_open:.4f}"
            )

    def on_position_changed(self, event: PositionChanged) -> None:
        """Handle position changed event."""
        position = event.position
        self._position_state.side = position.side
        self._position_state.quantity = position.quantity.as_double()
        self._position_state.unrealized_pnl = position.unrealized_pnl.as_double() if position.unrealized_pnl else 0.0

        if self.config.enable_logging:
            self.log.info(
                f"Position changed: side={position.side.name}, "
                f"qty={position.quantity}, unrealized_pnl={self._position_state.unrealized_pnl:.4f}"
            )

    def on_position_closed(self, event: PositionClosed) -> None:
        """Handle position closed event."""
        position = event.position
        realized_pnl = position.realized_pnl.as_double() if position.realized_pnl else 0.0

        # Record the trade - use position data when local state is missing
        entry_time = self._position_state.entry_time
        if entry_time is None:
            # Fallback to position open time if available
            entry_time = unix_nanos_to_dt(position.ts_opened)

        entry_side = self._position_state.side
        if entry_side is None:
            # Infer from position side - opposite of closing side
            entry_side = OrderSide.BUY if position.side.name == "SELL" else OrderSide.SELL

        entry_price = self._position_state.entry_price
        quantity = self._position_state.quantity

        # Safe pnl_pct calculation avoiding division by zero
        pnl_pct = 0.0
        if entry_price > 1e-10 and quantity > 1e-10:
            pnl_pct = realized_pnl / (entry_price * quantity)

        trade = TradeRecord(
            entry_time=entry_time,
            exit_time=unix_nanos_to_dt(position.ts_closed),
            side=entry_side,
            entry_price=entry_price,
            exit_price=position.avg_px_close,
            quantity=quantity,
            pnl=realized_pnl,
            pnl_pct=pnl_pct,
        )
        self._metrics.trades.append(trade)
        self._metrics.total_trades += 1
        self._metrics.total_pnl += realized_pnl

        if realized_pnl > 0:
            self._metrics.winning_trades += 1
        else:
            self._metrics.losing_trades += 1

        # Reset position state
        self._position_state = PositionState(instrument_id=self.instrument_id)
        self._position_state.realized_pnl = realized_pnl

        if self.config.enable_logging:
            self.log.info(
                f"Position closed: realized_pnl={realized_pnl:.4f}, "
                f"total_pnl={self._metrics.total_pnl:.4f}, "
                f"win_rate={self._metrics.win_rate:.2%}"
            )

    # Utility Methods

    def get_current_price(self) -> float | None:
        """Get current market price from quote or trade tick."""
        quote = self.cache.quote_tick(self.instrument_id)
        if quote:
            return (quote.bid_price.as_double() + quote.ask_price.as_double()) / 2

        trade = self.cache.trade_tick(self.instrument_id)
        if trade:
            return trade.price.as_double()

        return None

    def get_inventory(self) -> float:
        """Get current inventory (positive for long, negative for short)."""
        position = self.portfolio.net_position(self.instrument_id)
        if position:
            return float(position)
        return 0.0

    def is_within_position_limit(self, additional_qty: float = 0.0) -> bool:
        """Check if additional position is within limits."""
        current = abs(self.get_inventory())
        return (current + additional_qty) <= self.max_position_size

    # State Persistence

    def on_save(self) -> dict[str, Any]:
        """Save strategy state for recovery."""
        return {
            "position_state": {
                "side": self._position_state.side.name if self._position_state.side else None,
                "quantity": self._position_state.quantity,
                "entry_price": self._position_state.entry_price,
                "entry_time": self._position_state.entry_time.isoformat() if self._position_state.entry_time else None,
                "realized_pnl": self._position_state.realized_pnl,
            },
            "metrics": {
                "total_trades": self._metrics.total_trades,
                "winning_trades": self._metrics.winning_trades,
                "losing_trades": self._metrics.losing_trades,
                "total_pnl": self._metrics.total_pnl,
                "max_drawdown": self._metrics.max_drawdown,
                "total_fees": self._metrics.total_fees,
            },
        }

    def on_load(self, state: dict[str, Any]) -> None:
        """Restore strategy state."""
        if "position_state" in state:
            pos = state["position_state"]
            if pos.get("side"):
                self._position_state.side = OrderSide[pos["side"]]
            self._position_state.quantity = pos.get("quantity", 0.0)
            self._position_state.entry_price = pos.get("entry_price", 0.0)
            if pos.get("entry_time"):
                self._position_state.entry_time = datetime.fromisoformat(pos["entry_time"])
            self._position_state.realized_pnl = pos.get("realized_pnl", 0.0)

        if "metrics" in state:
            met = state["metrics"]
            self._metrics.total_trades = met.get("total_trades", 0)
            self._metrics.winning_trades = met.get("winning_trades", 0)
            self._metrics.losing_trades = met.get("losing_trades", 0)
            self._metrics.total_pnl = met.get("total_pnl", 0.0)
            self._metrics.max_drawdown = met.get("max_drawdown", 0.0)
            self._metrics.total_fees = met.get("total_fees", 0.0)

    def on_stop(self) -> None:
        """Called when strategy stops."""
        self._is_active = False
        self.cancel_all_open_orders()
        self.close_position()

        self.log.info(
            f"Strategy {self.id} stopped. "
            f"Total trades: {self._metrics.total_trades}, "
            f"Total P&L: {self._metrics.total_pnl:.4f}, "
            f"Win rate: {self._metrics.win_rate:.2%}"
        )

    def on_reset(self) -> None:
        """Reset strategy state."""
        self._position_state = PositionState(instrument_id=self.instrument_id)
        self._metrics = StrategyMetrics()
        self._pending_orders.clear()
        self.log.info(f"Strategy {self.id} reset")

    def on_dispose(self) -> None:
        """Final cleanup."""
        self.log.info(f"Strategy {self.id} disposed")
