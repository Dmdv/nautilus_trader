"""
Avellaneda-Stoikov Market Making Strategy.

Implements a market making strategy based on the Avellaneda-Stoikov framework
with inventory-based quote skewing, VPIN adverse selection detection,
and volatility-adaptive spreads.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import OrderBookDeltas, QuoteTick, TradeTick
from nautilus_trader.model.enums import AggressorSide, BookType, OrderSide, TimeInForce
from nautilus_trader.model.identifiers import ClientOrderId, InstrumentId
from nautilus_trader.trading.strategy import Strategy

from .risk import RiskConfig, RiskManager, VolatilityEstimator
from .signals import VPINSignalGenerator


class MarketMakingConfig(StrategyConfig, frozen=True):
    """
    Configuration for Avellaneda-Stoikov market making strategy.

    Attributes:
        instrument_id: The instrument identifier string.

        # Inventory management
        max_inventory: Maximum position size (both sides).
        inventory_target: Target inventory (0 = neutral).
        gamma: Risk aversion parameter for Avellaneda-Stoikov.

        # Spread parameters
        base_spread_bps: Base spread in basis points.
        min_spread_bps: Minimum spread in basis points.
        max_spread_bps: Maximum spread in basis points.
        spread_volatility_scalar: Spread multiplier based on volatility.

        # Order parameters
        max_order_size: Maximum order size.
        quote_levels: Number of quote levels on each side.
        level_spacing_bps: Spacing between quote levels in bps.

        # VPIN adverse selection
        vpin_threshold: VPIN threshold to pull quotes.
        vpin_bucket_size: Volume per VPIN bucket.
        vpin_num_buckets: Number of buckets for VPIN calculation.

        # Risk limits
        max_daily_loss_pct: Maximum daily loss percentage.

        # Execution
        refresh_interval_bars: Bars between quote refreshes.
        post_only: Whether quotes should be post-only.
        enable_logging: Enable detailed logging.
    """

    instrument_id: str

    # Inventory management
    max_inventory: float = 10.0
    inventory_target: float = 0.0
    gamma: float = 0.1  # Risk aversion

    # Spread parameters
    base_spread_bps: float = 5.0
    min_spread_bps: float = 2.0
    max_spread_bps: float = 50.0
    spread_volatility_scalar: float = 2.0

    # Order parameters
    max_order_size: str = "1.0"
    quote_levels: int = 1
    level_spacing_bps: float = 2.0

    # VPIN adverse selection
    vpin_threshold: float = 0.7
    vpin_bucket_size: float = 1000.0
    vpin_num_buckets: int = 50

    # Risk limits
    max_daily_loss_pct: float = 1.0

    # Execution
    refresh_interval_bars: int = 1
    post_only: bool = True
    enable_logging: bool = True


class MarketMakingStrategy(Strategy):
    """
    Avellaneda-Stoikov market making strategy.

    Implements optimal market making with:
    - Inventory-based quote skewing using reservation price
    - Volatility-adaptive spreads
    - VPIN-based adverse selection detection
    - Multi-level quoting

    Avellaneda-Stoikov Framework:
        Reservation price: r = s - q * gamma * sigma^2 * T
        Optimal spread: delta = gamma * sigma^2 * T + (2/gamma) * ln(1 + gamma/k)

    Where:
        s = mid price
        q = inventory
        gamma = risk aversion
        sigma = volatility
        T = time to terminal
        k = order arrival intensity

    VPIN (Volume-Synchronized Probability of Informed Trading):
        VPIN = |Buy Volume - Sell Volume| / Total Volume

    High VPIN indicates potential adverse selection from informed traders.
    """

    def __init__(self, config: MarketMakingConfig) -> None:
        """
        Initialize market making strategy.

        Args:
            config: Strategy configuration.
        """
        super().__init__(config)

        # Parse identifiers
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.max_order_size = Decimal(config.max_order_size)

        # Market state
        self._mid_price: float | None = None
        self._best_bid: float | None = None
        self._best_ask: float | None = None
        self._volatility: float | None = None

        # Volatility estimator
        self._volatility_estimator = VolatilityEstimator(
            lookback_period=20,
            ewma_lambda=0.94,
        )

        # VPIN signal generator
        self._vpin_generator = VPINSignalGenerator(
            bucket_size=config.vpin_bucket_size,
            num_buckets=config.vpin_num_buckets,
            threshold=config.vpin_threshold,
            name="VPIN",
        )

        # Risk manager
        self._risk_manager = RiskManager(
            RiskConfig(
                max_position_size=config.max_inventory,
                max_daily_loss_pct=config.max_daily_loss_pct,
            )
        )

        # Active orders tracking
        self._bid_orders: list[ClientOrderId] = []
        self._ask_orders: list[ClientOrderId] = []

        # State
        self._bar_count = 0
        self._quotes_pulled = False
        self._last_quote_update = 0

    @property
    def instrument(self):
        """Return the instrument from cache."""
        return self.cache.instrument(self.instrument_id)

    @property
    def vpin(self) -> float:
        """Return current VPIN value."""
        return self._vpin_generator.vpin

    @property
    def is_toxic(self) -> bool:
        """Return True if VPIN indicates adverse selection risk."""
        return self._vpin_generator.is_toxic

    def on_start(self) -> None:
        """Called when strategy starts."""
        # Subscribe to order book
        self.subscribe_order_book_deltas(
            instrument_id=self.instrument_id,
            book_type=BookType.L2_MBP,
            depth=10,
        )

        # Subscribe to trade ticks for VPIN
        self.subscribe_trade_ticks(self.instrument_id)

        # Subscribe to quote ticks
        self.subscribe_quote_ticks(self.instrument_id)

        self.log.info(
            f"Market making strategy started: {self.id}\n"
            f"  Instrument: {self.instrument_id}\n"
            f"  Max inventory: {self.config.max_inventory}\n"
            f"  Base spread: {self.config.base_spread_bps} bps\n"
            f"  VPIN threshold: {self.config.vpin_threshold}"
        )

    def on_quote_tick(self, tick: QuoteTick) -> None:
        """
        Handle quote tick update.

        Args:
            tick: Quote tick data.
        """
        bid = tick.bid_price.as_double()
        ask = tick.ask_price.as_double()
        self._best_bid = bid
        self._best_ask = ask

        if bid > 0 and ask > 0:
            self._mid_price = (bid + ask) / 2
            self._volatility_estimator.update_price(self._mid_price)
            self._volatility = self._volatility_estimator.ewma_volatility

    def on_order_book_deltas(self, deltas: OrderBookDeltas) -> None:
        """
        Handle order book update.

        Args:
            deltas: Order book delta updates (used to trigger update, actual data from cache).
        """
        _ = deltas  # Acknowledge parameter - we fetch book from cache for full state
        book = self.cache.order_book(self.instrument_id)
        if book is None:
            return

        # Update mid price from book
        best_bid = book.best_bid_price()
        best_ask = book.best_ask_price()

        if best_bid and best_ask:
            bid = best_bid.as_double()
            ask = best_ask.as_double()
            self._best_bid = bid
            self._best_ask = ask
            self._mid_price = (bid + ask) / 2

            # Check adverse selection before quoting
            if not self.is_toxic:
                self._update_quotes()
            elif not self._quotes_pulled:
                self._cancel_all_quotes()
                self._quotes_pulled = True
                if self.config.enable_logging:
                    self.log.warning(
                        f"VPIN {self.vpin:.3f} > threshold {self.config.vpin_threshold}, "
                        "pulling quotes"
                    )

    def on_trade_tick(self, tick: TradeTick) -> None:
        """
        Handle trade tick for VPIN calculation.

        Args:
            tick: Trade tick data.
        """
        size = tick.size.as_double()
        is_buyer = tick.aggressor_side == AggressorSide.BUYER

        # Update VPIN
        self._vpin_generator.add_trade(size, is_buyer)

        # Check if quotes should be restored
        if self._quotes_pulled and not self.is_toxic:
            self._quotes_pulled = False
            self._update_quotes()
            if self.config.enable_logging:
                self.log.info(f"VPIN normalized to {self.vpin:.3f}, restoring quotes")

    def _calculate_reservation_price(self) -> float:
        """
        Calculate Avellaneda-Stoikov reservation price.

        Formula:
            r = s - q * gamma * sigma^2 * T

        Where:
            s = mid price
            q = inventory (positive = long, negative = short)
            gamma = risk aversion parameter
            sigma = volatility
            T = time horizon (normalized to 1)

        Returns:
            Reservation price.
        """
        if self._mid_price is None:
            return 0.0

        inventory = self._get_inventory()
        # Use default volatility if not yet estimated
        if self._volatility is None:
            sigma = 0.02  # Default 2% daily vol
            if self.config.enable_logging:
                self.log.debug("Using default volatility (0.02) - not enough data for estimation")
        else:
            sigma = self._volatility
        gamma = self.config.gamma
        T = 1.0  # Normalized time horizon

        # r = s - q * gamma * sigma^2 * T
        reservation_price = self._mid_price - inventory * gamma * (sigma ** 2) * T

        return reservation_price

    def _calculate_optimal_spread(self) -> float:
        """
        Calculate optimal spread based on Avellaneda-Stoikov.

        Simplified formula:
            spread = base_spread * (1 + volatility_scalar * sigma)

        Clamped to [min_spread, max_spread].

        Returns:
            Optimal spread as decimal (not bps).
        """
        base_spread = self.config.base_spread_bps / 10000
        # Use default volatility if not yet estimated
        if self._volatility is None:
            sigma = 0.02  # Default 2% daily vol
        else:
            sigma = self._volatility

        # Adjust for volatility
        spread = base_spread * (1 + self.config.spread_volatility_scalar * sigma)

        # Clamp to limits
        min_spread = self.config.min_spread_bps / 10000
        max_spread = self.config.max_spread_bps / 10000

        return max(min_spread, min(spread, max_spread))

    def _calculate_inventory_skew(self) -> float:
        """
        Calculate quote skew based on inventory.

        Skew shifts quotes to reduce inventory:
        - Long inventory: lower bid, lower ask (sell pressure)
        - Short inventory: higher bid, higher ask (buy pressure)

        Returns:
            Skew adjustment (positive = shift quotes up).
        """
        inventory = self._get_inventory()
        target = self.config.inventory_target
        max_inv = self.config.max_inventory

        # Normalized inventory deviation
        if max_inv > 0:
            inv_deviation = (inventory - target) / max_inv
        else:
            inv_deviation = 0.0

        # Skew proportional to deviation
        # Negative skew for long inventory (encourage selling)
        # Use default volatility if not yet estimated
        if self._volatility is None:
            sigma = 0.02  # Default 2% daily vol
        else:
            sigma = self._volatility
        skew = -inv_deviation * self.config.gamma * (sigma ** 2)

        return skew

    def _get_inventory(self) -> float:
        """
        Get current inventory position.

        Returns:
            Position quantity (positive = long, negative = short).
        """
        position = self.cache.position_for_instrument(self.instrument_id)
        if position is not None:
            qty = position.quantity.as_double()
            return qty if position.is_long else -qty
        return 0.0

    def _update_quotes(self) -> None:
        """Update bid and ask quotes."""
        if self._mid_price is None:
            return

        # Check risk limits
        if not self._risk_manager.is_trading_allowed:
            self._cancel_all_quotes()
            return

        # Cancel existing quotes
        self._cancel_all_quotes()

        # Calculate quote parameters
        reservation_price = self._calculate_reservation_price()
        spread = self._calculate_optimal_spread()
        skew = self._calculate_inventory_skew()

        # Calculate quote prices
        # Reservation price replaces mid for skewed quotes
        bid_price = reservation_price - spread / 2 + skew
        ask_price = reservation_price + spread / 2 + skew

        # Get current inventory
        inventory = self._get_inventory()

        # Submit quotes at multiple levels
        for level in range(self.config.quote_levels):
            level_offset = level * (self.config.level_spacing_bps / 10000) * self._mid_price

            # Submit bid if not at max long
            if inventory < self.config.max_inventory:
                bid_level_price = bid_price - level_offset
                self._submit_bid(bid_level_price)

            # Submit ask if not at max short
            if inventory > -self.config.max_inventory:
                ask_level_price = ask_price + level_offset
                self._submit_ask(ask_level_price)

        if self.config.enable_logging:
            self.log.debug(
                f"Quotes updated:\n"
                f"  Mid: {self._mid_price:.4f}\n"
                f"  Reservation: {reservation_price:.4f}\n"
                f"  Spread: {spread * 10000:.2f} bps\n"
                f"  Skew: {skew:.6f}\n"
                f"  Inventory: {inventory:.4f}\n"
                f"  VPIN: {self.vpin:.3f}"
            )

    def _submit_bid(self, price: float) -> None:
        """
        Submit a bid order.

        Args:
            price: Bid price.
        """
        instrument = self.instrument
        if instrument is None:
            self.log.error("Cannot submit bid - instrument not found in cache")
            return

        order = self.order_factory.limit(
            instrument_id=self.instrument_id,
            order_side=OrderSide.BUY,
            quantity=instrument.make_qty(self.max_order_size),
            price=instrument.make_price(price),
            time_in_force=TimeInForce.GTC,
            post_only=self.config.post_only,
        )
        self.submit_order(order)
        self._bid_orders.append(order.client_order_id)

    def _submit_ask(self, price: float) -> None:
        """
        Submit an ask order.

        Args:
            price: Ask price.
        """
        instrument = self.instrument
        if instrument is None:
            self.log.error("Cannot submit ask - instrument not found in cache")
            return

        order = self.order_factory.limit(
            instrument_id=self.instrument_id,
            order_side=OrderSide.SELL,
            quantity=instrument.make_qty(self.max_order_size),
            price=instrument.make_price(price),
            time_in_force=TimeInForce.GTC,
            post_only=self.config.post_only,
        )
        self.submit_order(order)
        self._ask_orders.append(order.client_order_id)

    def _cancel_all_quotes(self) -> None:
        """Cancel all active quotes."""
        for order_id in self._bid_orders + self._ask_orders:
            order = self.cache.order(order_id)
            if order and order.is_open:
                self.cancel_order(order)

        self._bid_orders.clear()
        self._ask_orders.clear()

    def on_order_filled(self, event) -> None:
        """Handle order filled event."""
        order_id = event.client_order_id

        # Remove from tracking
        if order_id in self._bid_orders:
            self._bid_orders.remove(order_id)
        elif order_id in self._ask_orders:
            self._ask_orders.remove(order_id)

        if self.config.enable_logging:
            self.log.info(
                f"Quote filled: {event.order_side.name} "
                f"{event.last_qty} @ {event.last_px}"
            )

        # Update quotes after fill
        self._update_quotes()

    def on_order_canceled(self, event) -> None:
        """Handle order canceled event."""
        order_id = event.client_order_id

        if order_id in self._bid_orders:
            self._bid_orders.remove(order_id)
        elif order_id in self._ask_orders:
            self._ask_orders.remove(order_id)

    def on_position_changed(self, _event) -> None:
        """Handle position change - may need to adjust quotes."""
        # Recalculate quotes with new inventory (position data retrieved from portfolio)
        if not self._quotes_pulled:
            self._update_quotes()

    def on_save(self) -> dict[str, Any]:
        """Save strategy state."""
        return {
            "mid_price": self._mid_price,
            "volatility": self._volatility,
            "vpin": self.vpin,
            "bar_count": self._bar_count,
            "quotes_pulled": self._quotes_pulled,
        }

    def on_load(self, state: dict[str, Any]) -> None:
        """Load strategy state."""
        self._mid_price = state.get("mid_price")
        self._volatility = state.get("volatility")
        self._bar_count = state.get("bar_count", 0)
        self._quotes_pulled = state.get("quotes_pulled", False)

    def on_stop(self) -> None:
        """Called when strategy stops."""
        # Cancel all quotes
        self._cancel_all_quotes()

        # Close positions
        self.close_all_positions(self.instrument_id)

        self.log.info(
            f"Market making strategy stopped: {self.id}\n"
            f"  Final VPIN: {self.vpin:.3f}"
        )

    def on_reset(self) -> None:
        """Reset strategy state."""
        self._cancel_all_quotes()
        self._mid_price = None
        self._best_bid = None
        self._best_ask = None
        self._volatility = None
        self._vpin_generator.reset()
        self._volatility_estimator.reset()
        self._risk_manager.reset()
        self._bar_count = 0
        self._quotes_pulled = False

        self.log.info(f"Market making strategy reset: {self.id}")
