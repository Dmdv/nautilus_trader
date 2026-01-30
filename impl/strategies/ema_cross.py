"""
EMA Crossover Trend-Following Strategy.

Implements a classic exponential moving average crossover strategy
with proper NautilusTrader integration, position tracking, and
risk management.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from nautilus_trader.config import StrategyConfig
from nautilus_trader.indicators.average.ema import ExponentialMovingAverage
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from .risk import RiskConfig, RiskManager, VolatilityEstimator
from .signals import EMASignalGenerator, Signal


class EMACrossConfig(StrategyConfig, frozen=True):
    """
    Configuration for EMA Cross strategy.

    Attributes:
        instrument_id: The instrument identifier string.
        bar_type: The bar type string for data subscription.
        fast_period: Fast EMA period.
        slow_period: Slow EMA period.
        trade_size: Default trade size as string.
        max_position_size: Maximum allowed position size.
        risk_per_trade: Risk per trade as fraction of account.
        use_trailing_stop: Whether to use trailing stop.
        trailing_stop_atr_mult: ATR multiplier for trailing stop.
        atr_period: ATR period for volatility and stops.
        enable_logging: Whether to enable detailed logging.
    """

    instrument_id: str
    bar_type: str
    fast_period: int = 10
    slow_period: int = 20
    trade_size: str = "0.01"
    max_position_size: float = 10.0
    risk_per_trade: float = 0.02
    use_trailing_stop: bool = False
    trailing_stop_atr_mult: float = 2.0
    atr_period: int = 14
    enable_logging: bool = True


class EMACrossStrategy(Strategy):
    """
    EMA Crossover trend-following strategy.

    Generates signals based on fast EMA crossing slow EMA:
    - LONG: Fast EMA crosses above slow EMA (bullish crossover)
    - SHORT: Fast EMA crosses below slow EMA (bearish crossover)

    EMA Formula:
        EMA_t = alpha * price_t + (1 - alpha) * EMA_{t-1}
        where alpha = 2 / (period + 1)

    Features:
    - Proper NautilusTrader indicator integration
    - Position and P&L tracking
    - Risk management integration
    - Optional trailing stops
    - State persistence
    """

    def __init__(self, config: EMACrossConfig) -> None:
        """
        Initialize EMA Cross strategy.

        Args:
            config: Strategy configuration.
        """
        super().__init__(config)

        # Parse identifiers
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.bar_type = BarType.from_str(config.bar_type)
        self.trade_size = Decimal(config.trade_size)
        self.max_position_size = config.max_position_size

        # NautilusTrader indicators
        self.fast_ema = ExponentialMovingAverage(config.fast_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_period)

        # Signal generator (custom implementation for additional features)
        self._signal_generator = EMASignalGenerator(
            fast_period=config.fast_period,
            slow_period=config.slow_period,
            name="EMA_CROSS",
        )

        # Volatility estimator for ATR-based stops
        self._volatility_estimator = VolatilityEstimator(
            lookback_period=config.atr_period,
        )

        # Risk manager
        self._risk_manager = RiskManager(
            RiskConfig(
                max_position_size=config.max_position_size,
                risk_per_trade_pct=config.risk_per_trade * 100,
            )
        )

        # Internal state
        self._previous_fast: float | None = None
        self._previous_slow: float | None = None
        self._last_signal: Signal | None = None
        self._trailing_stop_price: float | None = None
        self._entry_price: float | None = None
        self._bar_count = 0

    @property
    def instrument(self):
        """Return the instrument from cache."""
        return self.cache.instrument(self.instrument_id)

    @property
    def is_initialized(self) -> bool:
        """Return True if indicators are initialized."""
        return self.slow_ema.initialized

    def on_start(self) -> None:
        """Called when strategy starts."""
        # Subscribe to bar data
        self.subscribe_bars(self.bar_type)

        self.log.info(
            f"EMA Cross strategy started: {self.id}\n"
            f"  Instrument: {self.instrument_id}\n"
            f"  Fast EMA: {self.config.fast_period}\n"
            f"  Slow EMA: {self.config.slow_period}\n"
            f"  Trade size: {self.trade_size}"
        )

    def on_bar(self, bar: Bar) -> None:
        """
        Handle bar data update.

        Args:
            bar: The bar data.
        """
        self._bar_count += 1

        # Get close price
        close = bar.close.as_double()

        # Update NautilusTrader indicators
        self.fast_ema.update_raw(close)
        self.slow_ema.update_raw(close)

        # Update custom signal generator (updates internal state)
        _ = self._signal_generator.update(close)

        # Update volatility estimator with OHLC
        self._volatility_estimator.update_ohlc(
            bar.open.as_double(),
            bar.high.as_double(),
            bar.low.as_double(),
            close,
        )

        # Update risk manager
        self._risk_manager.update_price(close)

        # Wait for initialization
        if not self.is_initialized:
            return

        # Store current values for crossover detection
        fast = self.fast_ema.value
        slow = self.slow_ema.value

        # Update trailing stop if enabled
        if self.config.use_trailing_stop:
            self._update_trailing_stop(bar)

        # Check for trading signals
        self._check_signal(fast, slow, close)

        # Store for next bar
        self._previous_fast = fast
        self._previous_slow = slow

    def _check_signal(self, fast: float, slow: float, price: float) -> None:
        """
        Check for EMA crossover signals.

        Args:
            fast: Current fast EMA value.
            slow: Current slow EMA value.
            price: Current price.
        """
        if self._previous_fast is None or self._previous_slow is None:
            return

        # Check risk limits
        if not self._risk_manager.is_trading_allowed:
            self.log.warning("Trading not allowed - risk limits breached")
            return

        # Bullish crossover: fast crosses above slow
        if self._previous_fast <= self._previous_slow and fast > slow:
            self._go_long(price)

        # Bearish crossover: fast crosses below slow
        elif self._previous_fast >= self._previous_slow and fast < slow:
            self._go_short(price)

        # Check trailing stop
        if self.config.use_trailing_stop and self._trailing_stop_price is not None:
            self._check_trailing_stop(price)

    def _go_long(self, price: float) -> None:
        """
        Enter long position.

        Args:
            price: Current price.
        """
        # Close any short position first
        if self.portfolio.is_net_short(self.instrument_id):
            self.close_all_positions(self.instrument_id)
            if self.config.enable_logging:
                self.log.info("Closed short position on bullish crossover")

        # Enter long if not already
        if not self.portfolio.is_net_long(self.instrument_id):
            # Check if within position limits
            current_position = self._get_position_quantity()
            allowed, reason = self._risk_manager.check_order(
                side="BUY",
                quantity=float(self.trade_size),
                price=price,
                current_position=current_position,
            )

            if not allowed:
                self.log.warning(f"Long order blocked: {reason}")
                return

            instrument = self.instrument
            if instrument is None:
                self.log.error("Cannot go long - instrument not found in cache")
                return

            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=instrument.make_qty(self.trade_size),
                time_in_force=TimeInForce.IOC,
            )
            self.submit_order(order)
            self._risk_manager.order_submitted()

            self._entry_price = price
            self._trailing_stop_price = None

            if self.config.enable_logging:
                self.log.info(
                    f"Bullish crossover - going long\n"
                    f"  Price: {price:.4f}\n"
                    f"  Fast EMA: {self.fast_ema.value:.4f}\n"
                    f"  Slow EMA: {self.slow_ema.value:.4f}"
                )

    def _go_short(self, price: float) -> None:
        """
        Enter short position.

        Args:
            price: Current price.
        """
        # Close any long position first
        if self.portfolio.is_net_long(self.instrument_id):
            self.close_all_positions(self.instrument_id)
            if self.config.enable_logging:
                self.log.info("Closed long position on bearish crossover")

        # Enter short if not already
        if not self.portfolio.is_net_short(self.instrument_id):
            # Check if within position limits
            current_position = self._get_position_quantity()
            allowed, reason = self._risk_manager.check_order(
                side="SELL",
                quantity=float(self.trade_size),
                price=price,
                current_position=current_position,
            )

            if not allowed:
                self.log.warning(f"Short order blocked: {reason}")
                return

            instrument = self.instrument
            if instrument is None:
                self.log.error("Cannot go short - instrument not found in cache")
                return

            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=instrument.make_qty(self.trade_size),
                time_in_force=TimeInForce.IOC,
            )
            self.submit_order(order)
            self._risk_manager.order_submitted()

            self._entry_price = price
            self._trailing_stop_price = None

            if self.config.enable_logging:
                self.log.info(
                    f"Bearish crossover - going short\n"
                    f"  Price: {price:.4f}\n"
                    f"  Fast EMA: {self.fast_ema.value:.4f}\n"
                    f"  Slow EMA: {self.slow_ema.value:.4f}"
                )

    def _update_trailing_stop(self, bar: Bar) -> None:
        """
        Update trailing stop price.

        Uses ATR-based trailing stop:
            Long: Stop = High - (ATR * multiplier)
            Short: Stop = Low + (ATR * multiplier)

        Note: Uses Parkinson volatility as a proxy for ATR. In production,
        consider using a proper ATR indicator for more accurate stop placement.

        Args:
            bar: Current bar.
        """
        volatility = self._volatility_estimator.parkinson_volatility()
        if volatility is None:
            return

        # Use volatility as a proxy for ATR
        # Conversion factor of 16 approximates daily-to-bar vol based on ~256 trading days/year
        atr_estimate = bar.close.as_double() * volatility / 16

        if self.portfolio.is_net_long(self.instrument_id):
            new_stop = bar.high.as_double() - (atr_estimate * self.config.trailing_stop_atr_mult)
            if self._trailing_stop_price is None or new_stop > self._trailing_stop_price:
                self._trailing_stop_price = new_stop

        elif self.portfolio.is_net_short(self.instrument_id):
            new_stop = bar.low.as_double() + (atr_estimate * self.config.trailing_stop_atr_mult)
            if self._trailing_stop_price is None or new_stop < self._trailing_stop_price:
                self._trailing_stop_price = new_stop

    def _check_trailing_stop(self, price: float) -> None:
        """
        Check if trailing stop is triggered.

        Args:
            price: Current price.
        """
        if self._trailing_stop_price is None:
            return

        if self.portfolio.is_net_long(self.instrument_id):
            if price <= self._trailing_stop_price:
                self.close_all_positions(self.instrument_id)
                self._trailing_stop_price = None
                if self.config.enable_logging:
                    self.log.info(f"Trailing stop triggered at {price:.4f}")

        elif self.portfolio.is_net_short(self.instrument_id):
            if price >= self._trailing_stop_price:
                self.close_all_positions(self.instrument_id)
                self._trailing_stop_price = None
                if self.config.enable_logging:
                    self.log.info(f"Trailing stop triggered at {price:.4f}")

    def _get_position_quantity(self) -> float:
        """Get current position quantity (signed)."""
        position = self.cache.position_for_instrument(self.instrument_id)
        if position is not None:
            qty = position.quantity.as_double()
            return qty if position.is_long else -qty
        return 0.0

    def on_order_filled(self, event) -> None:
        """Handle order filled event."""
        self._risk_manager.order_completed()

        if self.config.enable_logging:
            self.log.info(
                f"Order filled: {event.order_side.name} "
                f"{event.last_qty} @ {event.last_px}"
            )

    def on_position_closed(self, event) -> None:
        """Handle position closed event."""
        if event.position.realized_pnl:
            pnl = event.position.realized_pnl.as_double()
            self._risk_manager.update_daily_pnl(pnl)

            if self.config.enable_logging:
                self.log.info(f"Position closed: P&L = {pnl:.4f}")

    def on_save(self) -> dict[str, Any]:
        """Save strategy state for recovery."""
        return {
            "bar_count": self._bar_count,
            "previous_fast": self._previous_fast,
            "previous_slow": self._previous_slow,
            "trailing_stop_price": self._trailing_stop_price,
            "entry_price": self._entry_price,
            "fast_ema_value": self.fast_ema.value if self.fast_ema.initialized else None,
            "slow_ema_value": self.slow_ema.value if self.slow_ema.initialized else None,
        }

    def on_load(self, state: dict[str, Any]) -> None:
        """Restore strategy state."""
        self._bar_count = state.get("bar_count", 0)
        self._previous_fast = state.get("previous_fast")
        self._previous_slow = state.get("previous_slow")
        self._trailing_stop_price = state.get("trailing_stop_price")
        self._entry_price = state.get("entry_price")

    def on_stop(self) -> None:
        """Called when strategy stops."""
        # Cancel all open orders
        self.cancel_all_orders(self.instrument_id)

        # Optionally close all positions
        self.close_all_positions(self.instrument_id)

        self.log.info(
            f"EMA Cross strategy stopped: {self.id}\n"
            f"  Total bars processed: {self._bar_count}"
        )

    def on_reset(self) -> None:
        """Reset strategy state."""
        self.fast_ema.reset()
        self.slow_ema.reset()
        self._signal_generator.reset()
        self._volatility_estimator.reset()
        self._risk_manager.reset()
        self._previous_fast = None
        self._previous_slow = None
        self._trailing_stop_price = None
        self._entry_price = None
        self._bar_count = 0

        self.log.info(f"EMA Cross strategy reset: {self.id}")
