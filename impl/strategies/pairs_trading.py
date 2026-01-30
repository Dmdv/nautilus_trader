"""
Statistical Arbitrage Pairs Trading Strategy.

Implements pairs trading with cointegration testing, dynamic hedge ratios,
z-score based entry/exit, and half-life monitoring.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import numpy as np

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy

from .risk import RiskConfig, RiskManager
from .signals import SignalType, ZScoreSignalGenerator


class PairsTradingConfig(StrategyConfig, frozen=True):
    """
    Configuration for pairs trading strategy.

    Attributes:
        leg1_instrument: First leg instrument identifier.
        leg2_instrument: Second leg instrument identifier.
        leg1_bar_type: Bar type for leg 1.
        leg2_bar_type: Bar type for leg 2.

        # Cointegration parameters
        lookback_period: Days for cointegration test and regression.
        retest_frequency: Bars between cointegration retests.
        min_coint_pvalue: Maximum p-value for cointegration (lower = stricter).

        # Spread parameters
        zscore_entry: Z-score threshold for entry.
        zscore_exit: Z-score threshold for exit.
        zscore_stop: Z-score threshold for stop loss.

        # Half-life
        max_half_life_days: Maximum acceptable mean-reversion half-life.
        min_half_life_days: Minimum acceptable half-life (filter noise).

        # Position sizing
        trade_size: Base trade size for leg 1.
        max_position: Maximum position size per leg.

        # Hedge ratio
        hedge_ratio_method: Method for hedge ratio (ols, tls, kalman).
        hedge_ratio_update_freq: Bars between hedge ratio updates.

        # Risk
        max_spread_risk: Maximum risk per spread trade.
        enable_logging: Enable detailed logging.
    """

    leg1_instrument: str
    leg2_instrument: str
    leg1_bar_type: str
    leg2_bar_type: str

    # Cointegration parameters
    lookback_period: int = 252
    retest_frequency: int = 20
    min_coint_pvalue: float = 0.05

    # Spread parameters
    zscore_entry: float = 2.0
    zscore_exit: float = 0.5
    zscore_stop: float = 4.0

    # Half-life
    max_half_life_days: int = 30
    min_half_life_days: int = 1

    # Position sizing
    trade_size: str = "0.01"
    max_position: float = 1.0

    # Hedge ratio
    hedge_ratio_method: str = "ols"
    hedge_ratio_update_freq: int = 5

    # Risk
    max_spread_risk: float = 0.02
    enable_logging: bool = True


class PairsTradingStrategy(Strategy):
    """
    Statistical arbitrage pairs trading strategy.

    Uses cointegration to identify mean-reverting spread relationships
    and trades deviations from equilibrium.

    Cointegration Testing:
        Uses Engle-Granger two-step method:
        1. Regress leg1 = beta * leg2 + alpha + epsilon
        2. Test residuals for stationarity (ADF test)

    Hedge Ratio Estimation:
        OLS: leg1 = beta * leg2 (minimize RSS)
        Half-life: tau = -ln(2) / ln(theta)
        where theta is AR(1) coefficient of spread

    Z-Score Trading:
        z = (spread - mean) / std
        Long spread when z < -entry_threshold
        Short spread when z > entry_threshold
        Exit when |z| < exit_threshold
    """

    def __init__(self, config: PairsTradingConfig) -> None:
        """
        Initialize pairs trading strategy.

        Args:
            config: Strategy configuration.
        """
        super().__init__(config)

        # Parse identifiers
        self.leg1_id = InstrumentId.from_str(config.leg1_instrument)
        self.leg2_id = InstrumentId.from_str(config.leg2_instrument)
        self.leg1_bar_type = BarType.from_str(config.leg1_bar_type)
        self.leg2_bar_type = BarType.from_str(config.leg2_bar_type)
        self.trade_size = Decimal(config.trade_size)

        # Price history
        self._leg1_prices: list[float] = []
        self._leg2_prices: list[float] = []
        self._leg1_latest: float | None = None
        self._leg2_latest: float | None = None

        # Spread state
        self._hedge_ratio: float | None = None
        self._intercept: float | None = None
        self._spread_mean: float | None = None
        self._spread_std: float | None = None
        self._half_life: float | None = None

        # Cointegration state
        self._is_cointegrated = False
        self._coint_pvalue: float | None = None
        self._bars_since_coint_test = 0
        self._bars_since_hedge_update = 0

        # Z-score signal generator
        self._zscore_generator = ZScoreSignalGenerator(
            lookback_period=min(config.lookback_period, 60),
            entry_threshold=config.zscore_entry,
            exit_threshold=config.zscore_exit,
            stop_threshold=config.zscore_stop,
            name="SPREAD_ZSCORE",
        )

        # Risk manager
        self._risk_manager = RiskManager(
            RiskConfig(
                max_position_size=config.max_position,
                risk_per_trade_pct=config.max_spread_risk * 100,
            )
        )

        # Position state: 1 = long spread, -1 = short spread, 0 = flat
        self._spread_position = 0

        # Bar counters
        self._bar_count = 0

    @property
    def leg1_instrument(self):
        """Return leg 1 instrument from cache."""
        return self.cache.instrument(self.leg1_id)

    @property
    def leg2_instrument(self):
        """Return leg 2 instrument from cache."""
        return self.cache.instrument(self.leg2_id)

    @property
    def hedge_ratio(self) -> float | None:
        """Return current hedge ratio."""
        return self._hedge_ratio

    @property
    def half_life(self) -> float | None:
        """Return current half-life estimate in days."""
        return self._half_life

    @property
    def is_cointegrated(self) -> bool:
        """Return True if legs are currently cointegrated."""
        return self._is_cointegrated

    @property
    def zscore(self) -> float | None:
        """Return current spread z-score."""
        return self._zscore_generator.zscore

    def on_start(self) -> None:
        """Called when strategy starts."""
        # Subscribe to both legs
        self.subscribe_bars(self.leg1_bar_type)
        self.subscribe_bars(self.leg2_bar_type)

        self.log.info(
            f"Pairs trading strategy started: {self.id}\n"
            f"  Leg 1: {self.leg1_id}\n"
            f"  Leg 2: {self.leg2_id}\n"
            f"  Z-score entry: +/- {self.config.zscore_entry}\n"
            f"  Z-score exit: +/- {self.config.zscore_exit}"
        )

    def on_bar(self, bar: Bar) -> None:
        """
        Handle bar data update.

        Args:
            bar: The bar data.
        """
        self._bar_count += 1

        # Route to correct leg
        close = bar.close.as_double()

        if bar.bar_type.instrument_id == self.leg1_id:
            self._leg1_prices.append(close)
            self._leg1_latest = close
        elif bar.bar_type.instrument_id == self.leg2_id:
            self._leg2_prices.append(close)
            self._leg2_latest = close
        else:
            return

        # Keep history limited
        max_history = self.config.lookback_period * 2
        if len(self._leg1_prices) > max_history:
            self._leg1_prices = self._leg1_prices[-max_history:]
        if len(self._leg2_prices) > max_history:
            self._leg2_prices = self._leg2_prices[-max_history:]

        # Need synchronized prices
        if self._leg1_latest is None or self._leg2_latest is None:
            return

        if len(self._leg1_prices) != len(self._leg2_prices):
            # Prices not synchronized
            return

        if len(self._leg1_prices) < self.config.lookback_period:
            return

        # Periodic cointegration test
        self._bars_since_coint_test += 1
        if self._bars_since_coint_test >= self.config.retest_frequency:
            self._test_cointegration()
            self._bars_since_coint_test = 0

        if not self._is_cointegrated:
            return

        # Periodic hedge ratio update
        self._bars_since_hedge_update += 1
        if self._bars_since_hedge_update >= self.config.hedge_ratio_update_freq:
            self._update_hedge_ratio()
            self._bars_since_hedge_update = 0

        # Calculate current spread and z-score
        spread = self._calculate_spread(self._leg1_latest, self._leg2_latest)
        if spread is None:
            return

        # Update z-score generator
        self._zscore_generator.set_position(self._spread_position)
        signal = self._zscore_generator.update(spread)

        # Process signal
        if signal:
            self._process_signal(signal)

    def _test_cointegration(self) -> None:
        """
        Test for cointegration between legs using Engle-Granger method.

        Steps:
        1. Run OLS regression: leg1 = beta * leg2 + alpha
        2. Get residuals
        3. Test residuals for stationarity (ADF test)
        """
        try:
            # Use statsmodels for cointegration test
            from statsmodels.tsa.stattools import coint

            leg1 = np.array(self._leg1_prices[-self.config.lookback_period:])
            leg2 = np.array(self._leg2_prices[-self.config.lookback_period:])

            # Engle-Granger cointegration test
            _, pvalue, _ = coint(leg1, leg2)

            self._coint_pvalue = pvalue

            if pvalue < self.config.min_coint_pvalue:
                self._is_cointegrated = True
                self._update_hedge_ratio()
                self._estimate_half_life()

                if self.config.enable_logging:
                    hedge_str = f"{self._hedge_ratio:.4f}" if self._hedge_ratio is not None else "N/A"
                    half_life_str = f"{self._half_life:.1f}" if self._half_life is not None else "N/A"
                    self.log.info(
                        f"Cointegration confirmed:\n"
                        f"  p-value: {pvalue:.4f}\n"
                        f"  Hedge ratio: {hedge_str}\n"
                        f"  Half-life: {half_life_str} days"
                    )
            else:
                was_cointegrated = self._is_cointegrated
                self._is_cointegrated = False

                if was_cointegrated:
                    self.log.warning(
                        f"Cointegration lost: p-value={pvalue:.4f}\n"
                        "Closing spread position"
                    )
                    self._close_spread_position()

        except ImportError:
            # Fallback without statsmodels
            self._simple_cointegration_test()
        except Exception as e:
            self.log.error(f"Cointegration test failed: {e}")

    def _simple_cointegration_test(self) -> None:
        """
        Simple cointegration test without statsmodels.

        Uses correlation and spread stationarity heuristics.
        """
        leg1 = np.array(self._leg1_prices[-self.config.lookback_period:])
        leg2 = np.array(self._leg2_prices[-self.config.lookback_period:])

        # Check correlation
        correlation = np.corrcoef(leg1, leg2)[0, 1]

        if abs(correlation) < 0.7:
            self._is_cointegrated = False
            return

        # Estimate hedge ratio
        self._update_hedge_ratio()

        # Calculate spread
        spread = leg1 - self._hedge_ratio * leg2

        # Check if spread is mean-reverting (variance ratio test)
        half_n = len(spread) // 2
        var_1 = np.var(spread[:half_n])
        var_2 = np.var(spread[half_n:])

        # If variance is roughly stable, consider it mean-reverting
        variance_ratio = max(var_1, var_2) / min(var_1, var_2) if min(var_1, var_2) > 0 else float('inf')

        if variance_ratio < 2.0:
            self._is_cointegrated = True
            self._estimate_half_life()
        else:
            self._is_cointegrated = False

    def _update_hedge_ratio(self) -> None:
        """
        Update hedge ratio using OLS regression.

        OLS: leg1 = beta * leg2 + alpha + epsilon
        Minimize sum of squared residuals.
        """
        leg1 = np.array(self._leg1_prices[-self.config.lookback_period:])
        leg2 = np.array(self._leg2_prices[-self.config.lookback_period:])

        if self.config.hedge_ratio_method == "ols":
            # OLS regression
            X = np.column_stack([leg2, np.ones(len(leg2))])
            beta, _, _, _ = np.linalg.lstsq(X, leg1, rcond=None)
            self._hedge_ratio = beta[0]
            self._intercept = beta[1]

        elif self.config.hedge_ratio_method == "tls":
            # Total Least Squares (orthogonal regression)
            # More robust when both series have measurement error
            mean1, mean2 = np.mean(leg1), np.mean(leg2)
            leg1_centered = leg1 - mean1
            leg2_centered = leg2 - mean2

            cov_matrix = np.cov(leg1_centered, leg2_centered)
            eigenvalues, eigenvectors = np.linalg.eig(cov_matrix)
            min_idx = np.argmin(eigenvalues)
            self._hedge_ratio = -eigenvectors[0, min_idx] / eigenvectors[1, min_idx]
            self._intercept = mean1 - self._hedge_ratio * mean2

        else:
            # Default to OLS
            X = np.column_stack([leg2, np.ones(len(leg2))])
            beta, _, _, _ = np.linalg.lstsq(X, leg1, rcond=None)
            self._hedge_ratio = beta[0]
            self._intercept = beta[1]

        # Update spread statistics
        spread = self._calculate_spread_series()
        if spread is not None:
            self._spread_mean = np.mean(spread)
            self._spread_std = np.std(spread)

    def _estimate_half_life(self) -> None:
        """
        Estimate mean-reversion half-life using Ornstein-Uhlenbeck.

        Half-life = ln(2) / theta

        Where theta is estimated from AR(1) regression:
            spread_diff = -theta * spread_lag + epsilon
        """
        spread = self._calculate_spread_series()

        if spread is None or len(spread) < 20:
            self._half_life = None
            return

        # AR(1) regression for mean-reversion speed
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)

        # OLS: spread_diff = -theta * spread_lag
        denominator = np.sum(spread_lag ** 2)
        if denominator < 1e-10:
            self.log.warning("Cannot estimate half-life: zero spread variance")
            self._half_life = None
            self._is_cointegrated = False
            return

        theta = -np.sum(spread_diff * spread_lag) / denominator

        if theta > 0:
            self._half_life = np.log(2) / theta

            # Validate half-life is within acceptable range
            if self._half_life > self.config.max_half_life_days:
                if self.config.enable_logging:
                    self.log.warning(
                        f"Half-life {self._half_life:.1f} days exceeds maximum "
                        f"{self.config.max_half_life_days}"
                    )
                self._is_cointegrated = False

            elif self._half_life < self.config.min_half_life_days:
                if self.config.enable_logging:
                    self.log.warning(
                        f"Half-life {self._half_life:.1f} days below minimum "
                        f"{self.config.min_half_life_days}"
                    )
                self._is_cointegrated = False
        else:
            self._half_life = float('inf')
            self._is_cointegrated = False
            if self.config.enable_logging:
                self.log.warning("Spread is not mean-reverting (negative theta)")

    def _calculate_spread_series(self) -> np.ndarray | None:
        """
        Calculate spread time series.

        Spread = leg1 - hedge_ratio * leg2

        Returns:
            Spread array or None if not available.
        """
        if self._hedge_ratio is None:
            return None

        leg1 = np.array(self._leg1_prices[-self.config.lookback_period:])
        leg2 = np.array(self._leg2_prices[-self.config.lookback_period:])

        return leg1 - self._hedge_ratio * leg2

    def _calculate_spread(self, price1: float, price2: float) -> float | None:
        """
        Calculate current spread value.

        Args:
            price1: Leg 1 price.
            price2: Leg 2 price.

        Returns:
            Spread value or None.
        """
        if self._hedge_ratio is None:
            return None

        return price1 - self._hedge_ratio * price2

    def _process_signal(self, signal) -> None:
        """
        Process trading signal from z-score generator.

        Args:
            signal: Signal from ZScoreSignalGenerator.
        """
        if not self._risk_manager.is_trading_allowed:
            return

        if signal.signal_type == SignalType.LONG:
            # Spread too low - buy spread (long leg1, short leg2)
            self._enter_long_spread()

        elif signal.signal_type == SignalType.SHORT:
            # Spread too high - sell spread (short leg1, long leg2)
            self._enter_short_spread()

        elif signal.signal_type in (SignalType.EXIT_LONG, SignalType.EXIT_SHORT, SignalType.FLAT):
            self._close_spread_position()

    def _enter_long_spread(self) -> None:
        """
        Enter long spread position.

        Long spread = Long leg1 + Short leg2 (hedge-ratio adjusted)
        """
        if self._spread_position != 0:
            return

        if self._hedge_ratio is None:
            return

        leg1_instr = self.leg1_instrument
        leg2_instr = self.leg2_instrument
        if leg1_instr is None or leg2_instr is None:
            self.log.error("Cannot enter long spread - instruments not found in cache")
            return

        # Long leg1
        order1 = self.order_factory.market(
            instrument_id=self.leg1_id,
            order_side=OrderSide.BUY,
            quantity=leg1_instr.make_qty(self.trade_size),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(order1)

        # Short leg2 (hedge ratio adjusted quantity)
        hedge_qty = self.trade_size * Decimal(str(abs(self._hedge_ratio)))
        order2 = self.order_factory.market(
            instrument_id=self.leg2_id,
            order_side=OrderSide.SELL,
            quantity=leg2_instr.make_qty(hedge_qty),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(order2)

        self._spread_position = 1

        if self.config.enable_logging:
            zscore_str = f"{self.zscore:.2f}" if self.zscore is not None else "N/A"
            self.log.info(
                f"Entered long spread:\n"
                f"  Z-score: {zscore_str}\n"
                f"  Hedge ratio: {self._hedge_ratio:.4f}\n"
                f"  Leg1 qty: {self.trade_size}\n"
                f"  Leg2 qty: {hedge_qty}"
            )

    def _enter_short_spread(self) -> None:
        """
        Enter short spread position.

        Short spread = Short leg1 + Long leg2 (hedge-ratio adjusted)
        """
        if self._spread_position != 0:
            return

        if self._hedge_ratio is None:
            return

        leg1_instr = self.leg1_instrument
        leg2_instr = self.leg2_instrument
        if leg1_instr is None or leg2_instr is None:
            self.log.error("Cannot enter short spread - instruments not found in cache")
            return

        # Short leg1
        order1 = self.order_factory.market(
            instrument_id=self.leg1_id,
            order_side=OrderSide.SELL,
            quantity=leg1_instr.make_qty(self.trade_size),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(order1)

        # Long leg2 (hedge ratio adjusted quantity)
        hedge_qty = self.trade_size * Decimal(str(abs(self._hedge_ratio)))
        order2 = self.order_factory.market(
            instrument_id=self.leg2_id,
            order_side=OrderSide.BUY,
            quantity=leg2_instr.make_qty(hedge_qty),
            time_in_force=TimeInForce.IOC,
        )
        self.submit_order(order2)

        self._spread_position = -1

        if self.config.enable_logging:
            zscore_str = f"{self.zscore:.2f}" if self.zscore is not None else "N/A"
            self.log.info(
                f"Entered short spread:\n"
                f"  Z-score: {zscore_str}\n"
                f"  Hedge ratio: {self._hedge_ratio:.4f}\n"
                f"  Leg1 qty: {self.trade_size}\n"
                f"  Leg2 qty: {hedge_qty}"
            )

    def _close_spread_position(self) -> None:
        """Close spread position (both legs)."""
        if self._spread_position == 0:
            return

        self.close_all_positions(self.leg1_id)
        self.close_all_positions(self.leg2_id)

        if self.config.enable_logging:
            self.log.info(
                f"Closed spread position:\n"
                f"  Previous position: {'long' if self._spread_position == 1 else 'short'}\n"
                f"  Z-score: {self.zscore:.2f if self.zscore else 'N/A'}"
            )

        self._spread_position = 0

    def on_save(self) -> dict[str, Any]:
        """Save strategy state."""
        return {
            "bar_count": self._bar_count,
            "hedge_ratio": self._hedge_ratio,
            "intercept": self._intercept,
            "spread_mean": self._spread_mean,
            "spread_std": self._spread_std,
            "half_life": self._half_life,
            "is_cointegrated": self._is_cointegrated,
            "coint_pvalue": self._coint_pvalue,
            "spread_position": self._spread_position,
            "bars_since_coint_test": self._bars_since_coint_test,
            "leg1_prices": self._leg1_prices[-100:],  # Keep last 100
            "leg2_prices": self._leg2_prices[-100:],
        }

    def on_load(self, state: dict[str, Any]) -> None:
        """Load strategy state."""
        self._bar_count = state.get("bar_count", 0)
        self._hedge_ratio = state.get("hedge_ratio")
        self._intercept = state.get("intercept")
        self._spread_mean = state.get("spread_mean")
        self._spread_std = state.get("spread_std")
        self._half_life = state.get("half_life")
        self._is_cointegrated = state.get("is_cointegrated", False)
        self._coint_pvalue = state.get("coint_pvalue")
        self._spread_position = state.get("spread_position", 0)
        self._bars_since_coint_test = state.get("bars_since_coint_test", 0)
        self._leg1_prices = state.get("leg1_prices", [])
        self._leg2_prices = state.get("leg2_prices", [])

        # Restore z-score generator position
        self._zscore_generator.set_position(self._spread_position)

    def on_stop(self) -> None:
        """Called when strategy stops."""
        # Close spread position
        self._close_spread_position()

        hedge_str = f"{self._hedge_ratio:.4f}" if self._hedge_ratio is not None else "N/A"
        half_life_str = f"{self._half_life:.1f}" if self._half_life is not None else "N/A"
        self.log.info(
            f"Pairs trading strategy stopped: {self.id}\n"
            f"  Total bars: {self._bar_count}\n"
            f"  Final hedge ratio: {hedge_str}\n"
            f"  Final half-life: {half_life_str} days"
        )

    def on_reset(self) -> None:
        """Reset strategy state."""
        self._leg1_prices.clear()
        self._leg2_prices.clear()
        self._leg1_latest = None
        self._leg2_latest = None
        self._hedge_ratio = None
        self._intercept = None
        self._spread_mean = None
        self._spread_std = None
        self._half_life = None
        self._is_cointegrated = False
        self._coint_pvalue = None
        self._spread_position = 0
        self._bars_since_coint_test = 0
        self._bars_since_hedge_update = 0
        self._bar_count = 0
        self._zscore_generator.reset()
        self._risk_manager.reset()

        self.log.info(f"Pairs trading strategy reset: {self.id}")
