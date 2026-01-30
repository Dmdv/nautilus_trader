from decimal import Decimal
from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.enums import OrderSide, TimeInForce, BookType
from nautilus_trader.model.data import OrderBookDeltas

class MarketMakingConfig(StrategyConfig, frozen=True):
    """Market making strategy configuration."""
    instrument_id: str
    max_inventory: float = 10.0
    inventory_skew_factor: float = 0.001
    base_spread_bps: float = 5.0
    min_spread_bps: float = 2.0
    max_spread_bps: float = 50.0
    spread_volatility_scalar: float = 2.0
    max_order_size: str = "1.0"
    vpin_threshold: float = 0.7

class AvellanedaStoikovStrategy(Strategy):
    """
    Market making strategy using Avellaneda-Stoikov framework.
    """
    def __init__(self, config: MarketMakingConfig):
        super().__init__(config)
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.max_order_size = Decimal(config.max_order_size)
        self._mid_price = None
        self._volatility = 0.02 # Placeholder
        self._bid_orders = []
        self._ask_orders = []

    def on_start(self):
        self.subscribe_order_book_deltas(
            instrument_id=self.instrument_id,
            book_type=BookType.L2_MBP,
            depth=10,
        )
        self.subscribe_trade_ticks(self.instrument_id)
        self.log.info("Avellaneda-Stoikov strategy started")

    def on_order_book_deltas(self, deltas: OrderBookDeltas):
        book = self.cache.order_book(self.instrument_id)
        if book is None:
            return

        best_bid = book.best_bid_price()
        best_ask = book.best_ask_price()

        if best_bid and best_ask:
            self._mid_price = (best_bid.as_double() + best_ask.as_double()) / 2
            self._update_quotes()

    def _update_quotes(self):
        if self._mid_price is None:
            return

        # Cancel existing
        self._cancel_all_quotes()

        spread = self.config.base_spread_bps / 10000
        skew = 0.0 # Simplified

        bid_price = self._mid_price * (1 - spread / 2 + skew)
        ask_price = self._mid_price * (1 + spread / 2 + skew)

        # Submit Bid
        bid_order = self.order_factory.limit(
            instrument_id=self.instrument_id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.max_order_size),
            price=self.instrument.make_price(bid_price),
            time_in_force=TimeInForce.GTC,
            post_only=True,
        )
        self.submit_order(bid_order)
        self._bid_orders.append(bid_order.client_order_id)

        # Submit Ask
        ask_order = self.order_factory.limit(
            instrument_id=self.instrument_id,
            order_side=OrderSide.SELL,
            quantity=self.instrument.make_qty(self.max_order_size),
            price=self.instrument.make_price(ask_price),
            time_in_force=TimeInForce.GTC,
            post_only=True,
        )
        self.submit_order(ask_order)
        self._ask_orders.append(ask_order.client_order_id)

    def _cancel_all_quotes(self):
        for order_id in self._bid_orders + self._ask_orders:
            order = self.cache.order(order_id)
            if order and order.is_open:
                self.cancel_order(order)
        self._bid_orders = []
        self._ask_orders = []

    def on_stop(self):
        self._cancel_all_quotes()
        self.close_all_positions(self.instrument_id)
