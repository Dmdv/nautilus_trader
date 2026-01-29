# Strategy Development Guide

This guide covers building custom trading strategies for trend-following, market making, and statistical arbitrage.

---

## Strategy Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      NautilusTrader                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ DataEngine  │  │ ExecEngine  │  │    RiskEngine       │  │
│  │             │  │             │  │                     │  │
│  │ • Bars      │  │ • Orders    │  │ • Position limits   │  │
│  │ • Ticks     │  │ • Fills     │  │ • Exposure checks   │  │
│  │ • Books     │  │ • Positions │  │ • Pre-trade risk    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          │                                   │
│                    ┌─────▼─────┐                             │
│                    │  Strategy │                             │
│                    │           │                             │
│                    │ • Signals │                             │
│                    │ • Orders  │                             │
│                    │ • State   │                             │
│                    └───────────┘                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Strategy Anatomy

### Base Class

```python
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig

class MyStrategyConfig(StrategyConfig, frozen=True):
    """Configuration for MyStrategy."""
    instrument_id: str
    bar_type: str
    # Add strategy-specific parameters
    fast_period: int = 10
    slow_period: int = 20
    risk_per_trade: float = 0.02

class MyStrategy(Strategy):
    """Custom trading strategy."""

    def __init__(self, config: MyStrategyConfig):
        super().__init__(config)

        # Parse identifiers
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.bar_type = BarType.from_str(config.bar_type)

        # Initialize indicators
        self.fast_ema = ExponentialMovingAverage(config.fast_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_period)

        # Internal state
        self._last_signal = None

    def on_start(self):
        """Called when strategy starts."""
        # Subscribe to data
        self.subscribe_bars(self.bar_type)

        # Optional: Subscribe to additional data
        # self.subscribe_trade_ticks(self.instrument_id)
        # self.subscribe_quote_ticks(self.instrument_id)

    def on_bar(self, bar: Bar):
        """Called on each bar update."""
        # Update indicators
        self.fast_ema.update_raw(bar.close.as_double())
        self.slow_ema.update_raw(bar.close.as_double())

        # Wait for indicators to warm up
        if not self.slow_ema.initialized:
            return

        # Generate signal and execute
        self._check_signal()

    def on_order_filled(self, event: OrderFilled):
        """Called when order is filled."""
        self.log.info(f"Order filled: {event}")

    def on_position_changed(self, event: PositionChanged):
        """Called when position changes."""
        self.log.info(f"Position changed: {event}")

    def on_stop(self):
        """Called when strategy stops."""
        # Cancel all open orders
        self.cancel_all_orders(self.instrument_id)

        # Optionally close all positions
        self.close_all_positions(self.instrument_id)

    def _check_signal(self):
        """Check for trading signals."""
        # Implement your signal logic here
        pass
```

### Lifecycle Methods

| Method | When Called | Use For |
|--------|-------------|---------|
| `on_start()` | Strategy starts | Subscribe to data, initialize state |
| `on_stop()` | Strategy stops | Cancel orders, cleanup |
| `on_reset()` | Strategy reset | Reset indicators, clear state |
| `on_save()` | State persistence | Return state dict for recovery |
| `on_load()` | State restoration | Restore from saved state |
| `on_dispose()` | Final cleanup | Release resources |

### Data Handlers

| Method | Data Type | Use For |
|--------|-----------|---------|
| `on_bar(bar)` | Bar (OHLCV) | Trend strategies |
| `on_quote_tick(tick)` | Quote (bid/ask) | Spread analysis |
| `on_trade_tick(tick)` | Trade | Volume analysis |
| `on_order_book(book)` | Full book snapshot | Market making |
| `on_order_book_deltas(deltas)` | Book updates | Market making |
| `on_data(data)` | Custom data | Any custom feed |

### Order Management Handlers

| Method | When Called |
|--------|-------------|
| `on_order_submitted(event)` | Order sent to exchange |
| `on_order_accepted(event)` | Exchange accepted order |
| `on_order_rejected(event)` | Exchange rejected order |
| `on_order_filled(event)` | Order fully/partially filled |
| `on_order_canceled(event)` | Order canceled |
| `on_order_expired(event)` | Order expired |
| `on_order_pending_update(event)` | Order modification pending |
| `on_order_pending_cancel(event)` | Order cancellation pending |

### Position Handlers

| Method | When Called |
|--------|-------------|
| `on_position_opened(event)` | New position opened |
| `on_position_changed(event)` | Position quantity changed |
| `on_position_closed(event)` | Position fully closed |

---

## Trend-Following Strategy

### EMA Cross Strategy

```python
from decimal import Decimal
from nautilus_trader.config import StrategyConfig
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.indicators.average.ema import ExponentialMovingAverage
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.orders import MarketOrder

class EMACrossConfig(StrategyConfig, frozen=True):
    """Configuration for EMA Cross strategy."""
    instrument_id: str
    bar_type: str
    fast_period: int = 10
    slow_period: int = 20
    trade_size: str = "0.01"  # Base position size

class EMACrossStrategy(Strategy):
    """
    Simple EMA crossover strategy.

    Long when fast EMA crosses above slow EMA.
    Short when fast EMA crosses below slow EMA.
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
        self.log.info(f"Strategy started: {self.id}")

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
        # Close any short position first
        if self.portfolio.is_net_short(self.instrument_id):
            self.close_all_positions(self.instrument_id)

        # Enter long if not already
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
        # Close any long position first
        if self.portfolio.is_net_long(self.instrument_id):
            self.close_all_positions(self.instrument_id)

        # Enter short if not already
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
```

### Breakout Strategy

```python
class BreakoutConfig(StrategyConfig, frozen=True):
    instrument_id: str
    bar_type: str
    lookback_period: int = 20
    breakout_threshold: float = 1.0  # ATR multiplier
    trade_size: str = "0.01"

class BreakoutStrategy(Strategy):
    """
    Breakout strategy using Donchian channels.

    Long when price breaks above upper channel.
    Short when price breaks below lower channel.
    """

    def __init__(self, config: BreakoutConfig):
        super().__init__(config)

        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.bar_type = BarType.from_str(config.bar_type)
        self.trade_size = Decimal(config.trade_size)

        # Track highs and lows
        self._highs = []
        self._lows = []
        self._lookback = config.lookback_period

    def on_bar(self, bar: Bar):
        # Update rolling highs/lows
        self._highs.append(bar.high.as_double())
        self._lows.append(bar.low.as_double())

        if len(self._highs) > self._lookback:
            self._highs.pop(0)
            self._lows.pop(0)

        if len(self._highs) < self._lookback:
            return

        # Calculate channels
        upper_channel = max(self._highs[:-1])  # Exclude current bar
        lower_channel = min(self._lows[:-1])
        current_close = bar.close.as_double()

        # Breakout signals
        if current_close > upper_channel:
            self._enter_long()
        elif current_close < lower_channel:
            self._enter_short()
```

---

## Market Making Strategy

### Avellaneda-Stoikov Market Maker

```python
from nautilus_trader.model.data import OrderBookDeltas, TradeTick
from nautilus_trader.model.orders import LimitOrder
import numpy as np

class MarketMakingConfig(StrategyConfig, frozen=True):
    """Market making strategy configuration."""
    instrument_id: str

    # Inventory management
    max_inventory: float = 10.0           # Maximum position size
    inventory_target: float = 0.0         # Target inventory (neutral)
    inventory_skew_factor: float = 0.001  # Quote adjustment per unit

    # Spread parameters
    base_spread_bps: float = 5.0          # Base spread in basis points
    min_spread_bps: float = 2.0           # Minimum spread
    max_spread_bps: float = 50.0          # Maximum spread
    spread_volatility_scalar: float = 2.0 # Spread multiplier for volatility

    # Risk limits
    max_daily_loss_pct: float = 1.0       # Daily loss limit
    max_order_size: str = "1.0"           # Maximum order size

    # Execution
    quote_levels: int = 3                 # Number of quote levels
    level_spacing_bps: float = 2.0        # Spacing between levels
    refresh_interval_ms: int = 100        # Quote refresh interval

    # Adverse selection
    vpin_threshold: float = 0.7           # VPIN threshold to pull quotes

class MarketMakingStrategy(Strategy):
    """
    Market making strategy using Avellaneda-Stoikov framework.

    Features:
    - Inventory-based quote skewing
    - Volatility-adaptive spreads
    - VPIN-based adverse selection detection
    - Multi-level quoting
    """

    def __init__(self, config: MarketMakingConfig):
        super().__init__(config)

        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.max_order_size = Decimal(config.max_order_size)

        # Market state
        self._mid_price = None
        self._volatility = None
        self._vpin = 0.0

        # Trade flow tracking for VPIN
        self._buy_volume = 0.0
        self._sell_volume = 0.0
        self._volume_buckets = []

        # Active orders
        self._bid_orders = []
        self._ask_orders = []

    def on_start(self):
        # Subscribe to order book and trades
        self.subscribe_order_book_deltas(
            instrument_id=self.instrument_id,
            book_type=BookType.L2_MBP,
            depth=10,
        )
        self.subscribe_trade_ticks(self.instrument_id)

        self.log.info("Market making strategy started")

    def on_order_book_deltas(self, deltas: OrderBookDeltas):
        """Update quotes on book changes."""
        book = self.cache.order_book(self.instrument_id)
        if book is None:
            return

        # Calculate mid price
        best_bid = book.best_bid_price()
        best_ask = book.best_ask_price()

        if best_bid and best_ask:
            self._mid_price = (best_bid.as_double() + best_ask.as_double()) / 2

            # Update volatility estimate (simplified)
            self._update_volatility()

            # Check adverse selection
            if self._vpin < self.config.vpin_threshold:
                self._update_quotes()
            else:
                self._cancel_all_quotes()
                self.log.warning(f"VPIN {self._vpin:.2f} > threshold, pulling quotes")

    def on_trade_tick(self, tick: TradeTick):
        """Track trade flow for VPIN calculation."""
        size = tick.size.as_double()

        if tick.aggressor_side == AggressorSide.BUYER:
            self._buy_volume += size
        else:
            self._sell_volume += size

        self._update_vpin()

    def _update_vpin(self):
        """Calculate Volume-Synchronized Probability of Informed Trading."""
        total_volume = self._buy_volume + self._sell_volume

        if total_volume > 0:
            # VPIN = |Buy - Sell| / Total
            self._vpin = abs(self._buy_volume - self._sell_volume) / total_volume

        # Reset buckets periodically
        bucket_size = 1000  # Volume bucket size
        if total_volume > bucket_size:
            self._volume_buckets.append(self._vpin)
            self._buy_volume = 0
            self._sell_volume = 0

            # Keep last N buckets
            if len(self._volume_buckets) > 50:
                self._volume_buckets.pop(0)

    def _calculate_spread(self) -> float:
        """Calculate optimal spread based on inventory and volatility."""
        base_spread = self.config.base_spread_bps / 10000

        # Adjust for volatility
        if self._volatility:
            spread = base_spread * (1 + self.config.spread_volatility_scalar * self._volatility)
        else:
            spread = base_spread

        # Clamp to limits
        min_spread = self.config.min_spread_bps / 10000
        max_spread = self.config.max_spread_bps / 10000

        return max(min_spread, min(spread, max_spread))

    def _calculate_skew(self) -> float:
        """
        Calculate quote skew based on inventory.

        Avellaneda-Stoikov reservation price:
        r = s - q * gamma * sigma^2 * T

        Where:
        - s: mid price
        - q: inventory
        - gamma: risk aversion
        - sigma: volatility
        - T: time to end
        """
        inventory = self._get_inventory()
        gamma = self.config.inventory_skew_factor
        sigma = self._volatility or 0.01
        T = 1.0  # Simplified: assume constant time horizon

        skew = -gamma * inventory * (sigma ** 2) * T

        return skew

    def _get_inventory(self) -> float:
        """Get current inventory position."""
        position = self.portfolio.net_position(self.instrument_id)
        if position:
            return position.quantity.as_double()
        return 0.0

    def _update_quotes(self):
        """Update bid and ask quotes."""
        if self._mid_price is None:
            return

        # Cancel existing orders
        self._cancel_all_quotes()

        spread = self._calculate_spread()
        skew = self._calculate_skew()

        # Calculate quote prices with skew
        bid_price = self._mid_price * (1 - spread / 2 + skew)
        ask_price = self._mid_price * (1 + spread / 2 + skew)

        # Check inventory limits
        inventory = self._get_inventory()

        # Submit bid if not at max long
        if inventory < self.config.max_inventory:
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

        # Submit ask if not at max short
        if inventory > -self.config.max_inventory:
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
        """Cancel all active quotes."""
        for order_id in self._bid_orders + self._ask_orders:
            order = self.cache.order(order_id)
            if order and order.is_open:
                self.cancel_order(order)

        self._bid_orders = []
        self._ask_orders = []

    def _update_volatility(self):
        """Update volatility estimate (simplified)."""
        # In production, use proper volatility model (e.g., EWMA, GARCH)
        # This is a placeholder
        self._volatility = 0.02  # 2% daily vol

    def on_stop(self):
        self._cancel_all_quotes()
        self.close_all_positions(self.instrument_id)
```

---

## Statistical Arbitrage Strategy

### Pairs Trading with Cointegration

```python
from statsmodels.tsa.stattools import coint, adfuller
from statsmodels.regression.linear_model import OLS
import numpy as np
import pandas as pd

class StatArbConfig(StrategyConfig, frozen=True):
    """Statistical arbitrage configuration."""
    leg1_instrument: str
    leg2_instrument: str
    bar_type: str

    # Cointegration parameters
    lookback_period: int = 252           # Days for cointegration test
    retest_frequency: int = 20           # Days between retests
    min_coint_pvalue: float = 0.05       # Maximum p-value for cointegration

    # Spread parameters
    zscore_entry: float = 2.0            # Z-score to enter
    zscore_exit: float = 0.5             # Z-score to exit
    zscore_stop: float = 4.0             # Z-score stop loss

    # Half-life
    max_half_life_days: int = 30         # Maximum acceptable half-life

    # Position sizing
    trade_size: str = "0.01"
    max_position: float = 1.0

    # Hedge ratio
    hedge_ratio_method: str = "ols"      # ols, tls, or kalman

class StatArbStrategy(Strategy):
    """
    Pairs trading strategy using cointegration.

    Features:
    - Johansen/Engle-Granger cointegration testing
    - Dynamic hedge ratio (OLS or Kalman filter)
    - Z-score based entry/exit
    - Half-life monitoring
    """

    def __init__(self, config: StatArbConfig):
        super().__init__(config)

        self.leg1_id = InstrumentId.from_str(config.leg1_instrument)
        self.leg2_id = InstrumentId.from_str(config.leg2_instrument)
        self.bar_type = BarType.from_str(config.bar_type)
        self.trade_size = Decimal(config.trade_size)

        # Price history
        self._leg1_prices = []
        self._leg2_prices = []

        # Spread state
        self._hedge_ratio = None
        self._spread_mean = None
        self._spread_std = None
        self._half_life = None

        # Cointegration state
        self._is_cointegrated = False
        self._last_coint_test = 0
        self._bars_since_test = 0

        # Position state
        self._spread_position = 0  # +1 long spread, -1 short spread, 0 flat

    def on_start(self):
        # Subscribe to both legs
        bar_type_leg1 = BarType.from_str(
            f"{self.leg1_id}-1-MINUTE-LAST-EXTERNAL"
        )
        bar_type_leg2 = BarType.from_str(
            f"{self.leg2_id}-1-MINUTE-LAST-EXTERNAL"
        )

        self.subscribe_bars(bar_type_leg1)
        self.subscribe_bars(bar_type_leg2)

        self.log.info(f"Stat arb started: {self.leg1_id} vs {self.leg2_id}")

    def on_bar(self, bar: Bar):
        # Route to correct leg
        if bar.bar_type.instrument_id == self.leg1_id:
            self._leg1_prices.append(bar.close.as_double())
        elif bar.bar_type.instrument_id == self.leg2_id:
            self._leg2_prices.append(bar.close.as_double())

        # Keep history limited
        max_history = self.config.lookback_period * 2
        if len(self._leg1_prices) > max_history:
            self._leg1_prices = self._leg1_prices[-max_history:]
            self._leg2_prices = self._leg2_prices[-max_history:]

        # Need both prices
        if len(self._leg1_prices) != len(self._leg2_prices):
            return

        if len(self._leg1_prices) < self.config.lookback_period:
            return

        # Periodic cointegration test
        self._bars_since_test += 1
        if self._bars_since_test >= self.config.retest_frequency:
            self._test_cointegration()
            self._bars_since_test = 0

        if not self._is_cointegrated:
            return

        # Update hedge ratio and spread
        self._update_hedge_ratio()
        zscore = self._calculate_zscore()

        if zscore is None:
            return

        # Trading logic
        self._check_signals(zscore)

    def _test_cointegration(self):
        """Test for cointegration between legs."""
        leg1 = np.array(self._leg1_prices[-self.config.lookback_period:])
        leg2 = np.array(self._leg2_prices[-self.config.lookback_period:])

        # Engle-Granger cointegration test
        score, pvalue, _ = coint(leg1, leg2)

        if pvalue < self.config.min_coint_pvalue:
            self._is_cointegrated = True
            self._estimate_half_life()
            self.log.info(f"Cointegrated: p-value={pvalue:.4f}, half-life={self._half_life:.1f} days")
        else:
            self._is_cointegrated = False
            self.log.warning(f"Not cointegrated: p-value={pvalue:.4f}")

            # Close positions if relationship breaks down
            if self._spread_position != 0:
                self._close_spread_position()

    def _estimate_half_life(self):
        """Estimate mean-reversion half-life using Ornstein-Uhlenbeck."""
        spread = self._calculate_spread_series()

        if spread is None or len(spread) < 20:
            return

        # Regress spread_diff on spread_lag
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)

        # OLS regression
        X = spread_lag.reshape(-1, 1)
        model = OLS(spread_diff, X)
        result = model.fit()

        theta = -result.params[0]

        if theta > 0:
            self._half_life = np.log(2) / theta
        else:
            self._half_life = float('inf')
            self._is_cointegrated = False
            self.log.warning("Negative theta - spread is not mean-reverting")

    def _update_hedge_ratio(self):
        """Update hedge ratio using OLS."""
        leg1 = np.array(self._leg1_prices[-self.config.lookback_period:])
        leg2 = np.array(self._leg2_prices[-self.config.lookback_period:])

        # OLS: leg1 = beta * leg2 + alpha + epsilon
        X = leg2.reshape(-1, 1)
        model = OLS(leg1, X)
        result = model.fit()

        self._hedge_ratio = result.params[0]

    def _calculate_spread_series(self) -> np.ndarray:
        """Calculate spread time series."""
        if self._hedge_ratio is None:
            return None

        leg1 = np.array(self._leg1_prices[-self.config.lookback_period:])
        leg2 = np.array(self._leg2_prices[-self.config.lookback_period:])

        spread = leg1 - self._hedge_ratio * leg2
        return spread

    def _calculate_zscore(self) -> float:
        """Calculate current spread z-score."""
        spread = self._calculate_spread_series()

        if spread is None:
            return None

        self._spread_mean = np.mean(spread)
        self._spread_std = np.std(spread)

        if self._spread_std == 0:
            return None

        current_spread = spread[-1]
        zscore = (current_spread - self._spread_mean) / self._spread_std

        return zscore

    def _check_signals(self, zscore: float):
        """Check for entry/exit signals."""
        # Stop loss
        if abs(zscore) > self.config.zscore_stop:
            if self._spread_position != 0:
                self.log.warning(f"Stop loss triggered: z={zscore:.2f}")
                self._close_spread_position()
            return

        # Exit signal
        if self._spread_position != 0:
            if abs(zscore) < self.config.zscore_exit:
                self.log.info(f"Exit signal: z={zscore:.2f}")
                self._close_spread_position()
            return

        # Entry signals
        if zscore > self.config.zscore_entry:
            # Spread too high - short spread (short leg1, long leg2)
            self._enter_short_spread()

        elif zscore < -self.config.zscore_entry:
            # Spread too low - long spread (long leg1, short leg2)
            self._enter_long_spread()

    def _enter_long_spread(self):
        """Enter long spread position."""
        if self._spread_position != 0:
            return

        # Long leg1
        order1 = self.order_factory.market(
            instrument_id=self.leg1_id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.trade_size),
        )
        self.submit_order(order1)

        # Short leg2 (hedge ratio adjusted)
        hedge_qty = self.trade_size * Decimal(str(self._hedge_ratio))
        order2 = self.order_factory.market(
            instrument_id=self.leg2_id,
            order_side=OrderSide.SELL,
            quantity=self.instrument.make_qty(hedge_qty),
        )
        self.submit_order(order2)

        self._spread_position = 1
        self.log.info("Entered long spread")

    def _enter_short_spread(self):
        """Enter short spread position."""
        if self._spread_position != 0:
            return

        # Short leg1
        order1 = self.order_factory.market(
            instrument_id=self.leg1_id,
            order_side=OrderSide.SELL,
            quantity=self.instrument.make_qty(self.trade_size),
        )
        self.submit_order(order1)

        # Long leg2 (hedge ratio adjusted)
        hedge_qty = self.trade_size * Decimal(str(self._hedge_ratio))
        order2 = self.order_factory.market(
            instrument_id=self.leg2_id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(hedge_qty),
        )
        self.submit_order(order2)

        self._spread_position = -1
        self.log.info("Entered short spread")

    def _close_spread_position(self):
        """Close spread position."""
        self.close_all_positions(self.leg1_id)
        self.close_all_positions(self.leg2_id)
        self._spread_position = 0
        self.log.info("Closed spread position")

    def on_stop(self):
        self._close_spread_position()
```

---

## Project Structure

```
strategies/
├── __init__.py
├── base/
│   ├── __init__.py
│   ├── risk_manager.py       # Position sizing, risk limits
│   └── circuit_breaker.py    # Emergency shutdown logic
├── trend/
│   ├── __init__.py
│   ├── ema_cross.py          # EMA crossover
│   ├── breakout.py           # Donchian breakout
│   └── momentum.py           # Momentum/RSI based
├── market_making/
│   ├── __init__.py
│   ├── basic_mm.py           # Simple spread capture
│   ├── avellaneda_stoikov.py # A-S market making
│   └── vpin.py               # VPIN calculation
├── arb/
│   ├── __init__.py
│   ├── pairs_trading.py      # Cointegration-based
│   ├── funding_arb.py        # Funding rate arbitrage
│   └── cross_exchange.py     # Cross-venue arbitrage
├── utils/
│   ├── __init__.py
│   ├── indicators.py         # Custom indicators
│   └── signals.py            # Signal generation helpers
└── configs/
    ├── ema_cross_btc.yaml
    ├── mm_binance.yaml
    └── pairs_btc_eth.yaml
```

---

## Configuration Files

### YAML Configuration

```yaml
# configs/ema_cross_btc.yaml
strategy_id: "EMA-CROSS-001"
strategy_type: "EMACrossStrategy"

instrument_id: "BTCUSDT-PERP.BINANCE"
bar_type: "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL"

parameters:
  fast_period: 10
  slow_period: 20
  trade_size: "0.01"
```

### Loading Configuration

```python
import yaml
from pathlib import Path

def load_strategy_config(config_path: str) -> dict:
    """Load strategy configuration from YAML."""
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return config

# Usage
config_dict = load_strategy_config("configs/ema_cross_btc.yaml")
strategy_config = EMACrossConfig(**config_dict["parameters"])
```

---

## Best Practices

### 1. State Management

```python
def on_save(self) -> dict:
    """Save strategy state for recovery."""
    return {
        "last_signal": self._last_signal,
        "position_entry_price": self._entry_price,
        "indicators": {
            "fast_ema": self.fast_ema.value,
            "slow_ema": self.slow_ema.value,
        }
    }

def on_load(self, state: dict):
    """Restore strategy state."""
    self._last_signal = state.get("last_signal")
    self._entry_price = state.get("position_entry_price")
```

### 2. Error Handling

```python
def on_order_rejected(self, event: OrderRejected):
    """Handle order rejection gracefully."""
    self.log.error(f"Order rejected: {event.reason}")

    # Retry logic or alternative action
    if "insufficient balance" in event.reason.lower():
        self._reduce_position_size()
    elif "rate limit" in event.reason.lower():
        self._backoff_order_submission()
```

### 3. Position Sizing

```python
def _calculate_position_size(self, signal_strength: float) -> Decimal:
    """Calculate position size based on risk."""
    account_value = self.portfolio.account(self.venue).balance_total()
    risk_per_trade = self.config.risk_per_trade

    # Risk-based sizing
    risk_amount = account_value * risk_per_trade

    # ATR-based stop distance
    atr = self._atr.value
    stop_distance = atr * 2

    # Position size = Risk / Stop Distance
    if stop_distance > 0:
        position_size = risk_amount / stop_distance
    else:
        position_size = self.config.default_size

    return min(position_size, self.config.max_position)
```

### 4. Logging

```python
# Use structured logging
self.log.info(f"Signal: {signal}, Price: {price}, Size: {size}")
self.log.debug(f"Indicator values: fast={self.fast_ema.value:.4f}, slow={self.slow_ema.value:.4f}")
self.log.warning(f"Approaching position limit: {current}/{max_position}")
self.log.error(f"Order failed: {error}")
```

---

## Testing Strategies

### Unit Testing

```python
import pytest
from nautilus_trader.test_kit.stubs import TestStubs

def test_ema_cross_signal():
    """Test EMA crossover signal generation."""
    config = EMACrossConfig(
        instrument_id="BTCUSDT-PERP.BINANCE",
        bar_type="BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL",
        fast_period=2,
        slow_period=3,
    )
    strategy = EMACrossStrategy(config)

    # Create test bars
    bars = TestStubs.bar_list()

    # Feed bars to strategy
    for bar in bars:
        strategy.on_bar(bar)

    # Assert expected behavior
    assert strategy.fast_ema.initialized
    assert strategy.slow_ema.initialized
```

### Backtesting

See [BACKTESTING.md](BACKTESTING.md) for comprehensive backtesting guidance.

---

## Next Steps

1. **Backtest your strategy**: [BACKTESTING.md](BACKTESTING.md)
2. **Validate quantitatively**: [QUANTITATIVE_VALIDATION.md](QUANTITATIVE_VALIDATION.md)
3. **Deploy to production**: [DEPLOYMENT.md](DEPLOYMENT.md)
