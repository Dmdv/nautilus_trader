from decimal import Decimal
import numpy as np
from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide

class StatArbConfig(StrategyConfig, frozen=True):
    leg1_instrument: str
    leg2_instrument: str
    bar_type: str
    trade_size: str = "0.01"
    lookback_period: int = 20
    zscore_entry: float = 2.0
    zscore_exit: float = 0.5

class StatArbStrategy(Strategy):
    """
    Simple Pairs Trading Strategy.
    """
    def __init__(self, config: StatArbConfig):
        super().__init__(config)
        self.leg1_id = InstrumentId.from_str(config.leg1_instrument)
        self.leg2_id = InstrumentId.from_str(config.leg2_instrument)
        self.trade_size = Decimal(config.trade_size)
        
        self._leg1_prices = []
        self._leg2_prices = []
        self._spread_position = 0

    def on_start(self):
        self.subscribe_bars(BarType.from_str(f"{self.leg1_id}-1-MINUTE-LAST-EXTERNAL"))
        self.subscribe_bars(BarType.from_str(f"{self.leg2_id}-1-MINUTE-LAST-EXTERNAL"))
        self.log.info("StatArb strategy started")

    def on_bar(self, bar: Bar):
        if bar.bar_type.instrument_id == self.leg1_id:
            self._leg1_prices.append(bar.close.as_double())
        elif bar.bar_type.instrument_id == self.leg2_id:
            self._leg2_prices.append(bar.close.as_double())

        # Sync lengths (simplified)
        min_len = min(len(self._leg1_prices), len(self._leg2_prices))
        if min_len < self.config.lookback_period:
            return

        # Calculate Spread Z-Score
        leg1 = np.array(self._leg1_prices[-self.config.lookback_period:])
        leg2 = np.array(self._leg2_prices[-self.config.lookback_period:])
        
        # Simple ratio spread
        spread = leg1 / leg2
        zscore = (spread[-1] - np.mean(spread)) / np.std(spread)

        if self._spread_position == 0:
            if zscore > self.config.zscore_entry:
                self._enter_short_spread()
            elif zscore < -self.config.zscore_entry:
                self._enter_long_spread()
        else:
            if abs(zscore) < self.config.zscore_exit:
                self._close_spread()

    def _enter_long_spread(self):
        # Long leg1, Short leg2
        self.submit_order(self.order_factory.market(self.leg1_id, OrderSide.BUY, self.instrument.make_qty(self.trade_size)))
        self.submit_order(self.order_factory.market(self.leg2_id, OrderSide.SELL, self.instrument.make_qty(self.trade_size))) # Simplified hedging
        self._spread_position = 1

    def _enter_short_spread(self):
        # Short leg1, Long leg2
        self.submit_order(self.order_factory.market(self.leg1_id, OrderSide.SELL, self.instrument.make_qty(self.trade_size)))
        self.submit_order(self.order_factory.market(self.leg2_id, OrderSide.BUY, self.instrument.make_qty(self.trade_size)))
        self._spread_position = -1

    def _close_spread(self):
        self.close_all_positions(self.leg1_id)
        self.close_all_positions(self.leg2_id)
        self._spread_position = 0

    def on_stop(self):
        self._close_spread()
