from decimal import Decimal
from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.indicators import ExponentialMovingAverage
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.data import Bar, BarType

class EMACrossConfig(StrategyConfig, frozen=True):
    """Configuration for EMA Cross strategy."""
    instrument_id: str
    bar_type: str
    fast_period: int = 10
    slow_period: int = 20
    trade_size: str = "0.01"

class EMACrossStrategy(Strategy):
    """
    Simple EMA crossover strategy.
    """

    def __init__(self, config: EMACrossConfig):
        super().__init__(config)

        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.bar_type = BarType.from_str(config.bar_type)
        self.trade_size = Decimal(config.trade_size)

        # Indicators
        self.fast_ema = ExponentialMovingAverage(config.fast_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_period)

        # State
        self._previous_fast = None
        self._previous_slow = None

    def on_start(self):
        self.subscribe_bars(self.bar_type)
        self.log.info(f"Strategy started: {self.instrument_id}")

    def on_bar(self, bar: Bar):
        # Update indicators
        close = bar.close.as_double()
        self.fast_ema.update_raw(close)
        self.slow_ema.update_raw(close)

        if not self.slow_ema.initialized:
            return

        fast = self.fast_ema.value
        slow = self.slow_ema.value

        # Check for crossover
        if self._previous_fast is not None:
            # Bullish crossover
            if self._previous_fast <= self._previous_slow and fast > slow:
                self._go_long()

            # Bearish crossover
            elif self._previous_fast >= self._previous_slow and fast < slow:
                self._go_short()

        # Store for next bar
        self._previous_fast = fast
        self._previous_slow = slow

    def _go_long(self):
        """Enter long position."""
        if self.portfolio.is_net_short(self.instrument_id):
            self.close_all_positions(self.instrument_id)

        if not self.portfolio.is_net_long(self.instrument_id):
            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(self.trade_size),
                time_in_force=TimeInForce.IOC,
            )
            self.submit_order(order)
            self.log.info("Bullish crossover - going long")

    def _go_short(self):
        """Enter short position."""
        if self.portfolio.is_net_long(self.instrument_id):
            self.close_all_positions(self.instrument_id)

        if not self.portfolio.is_net_short(self.instrument_id):
            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=self.instrument.make_qty(self.trade_size),
                time_in_force=TimeInForce.IOC,
            )
            self.submit_order(order)
            self.log.info("Bearish crossover - going short")

    def on_stop(self):
        self.cancel_all_orders(self.instrument_id)
        self.close_all_positions(self.instrument_id)
