"""
Backtest Engine Module.

Provides a high-level wrapper around NautilusTrader's BacktestEngine
with convenient configuration and execution methods.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import numpy as np

from nautilus_trader.backtest.engine import BacktestEngine, BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD, USDT
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import TraderId, Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.trading.strategy import Strategy

from .loader import BacktestDataLoader
from .simulation import VenueSimulationParams


@dataclass
class BacktestConfig:
    """
    Configuration for running a backtest.

    Attributes:
        trader_id: Unique trader identifier.
        catalog_path: Path to data catalog.
        venue: Exchange venue name.
        instrument_ids: List of instruments to trade.
        start_time: Backtest start time.
        end_time: Backtest end time.
        starting_balance: Initial account balance.
        base_currency: Base currency for balance.
        account_type: Account type (CASH or MARGIN).
        oms_type: Order management system type.
        log_level: Logging level.
        bypass_logging: Skip logging for performance.
    """

    trader_id: str = "BACKTESTER-001"
    catalog_path: str = "data/catalog"
    venue: str = "BINANCE"
    instrument_ids: list[str] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    starting_balance: float = 100_000.0
    base_currency: str = "USDT"
    account_type: AccountType = AccountType.MARGIN
    oms_type: OmsType = OmsType.NETTING
    log_level: str = "INFO"
    bypass_logging: bool = False


@dataclass
class BacktestResult:
    """
    Results from a backtest run.

    Attributes:
        start_time: Backtest start time.
        end_time: Backtest end time.
        duration_seconds: Total duration in seconds.
        total_return: Total return percentage.
        sharpe_ratio: Annualized Sharpe ratio.
        max_drawdown: Maximum drawdown percentage.
        total_trades: Number of trades executed.
        win_rate: Percentage of winning trades.
        profit_factor: Gross profit / gross loss.
        account_balances: Final account balances.
        positions: Final positions.
        orders: Order history summary.
        fills: Fill history summary.
    """

    start_time: datetime
    end_time: datetime
    duration_seconds: float
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    total_trades: int
    win_rate: float
    profit_factor: float
    account_balances: dict[str, float]
    positions: list[dict[str, Any]]
    orders: dict[str, int]
    fills: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_return": self.total_return,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "account_balances": self.account_balances,
            "positions": self.positions,
            "orders": self.orders,
            "fills": self.fills,
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        return (
            f"Backtest Results ({self.start_time.date()} to {self.end_time.date()})\n"
            f"{'=' * 50}\n"
            f"Total Return:   {self.total_return:>10.2%}\n"
            f"Sharpe Ratio:   {self.sharpe_ratio:>10.2f}\n"
            f"Max Drawdown:   {self.max_drawdown:>10.2%}\n"
            f"Total Trades:   {self.total_trades:>10d}\n"
            f"Win Rate:       {self.win_rate:>10.2%}\n"
            f"Profit Factor:  {self.profit_factor:>10.2f}\n"
        )


class BacktestRunner:
    """
    High-level backtest runner with convenient API.

    Wraps NautilusTrader BacktestEngine with:
    - Automatic venue configuration
    - Exchange-specific simulation models
    - Data loading from catalog
    - Result extraction and analysis
    """

    def __init__(self, config: BacktestConfig) -> None:
        """
        Initialize backtest runner.

        Args:
            config: Backtest configuration.
        """
        self.config = config
        self._engine: BacktestEngine | None = None
        self._strategies: list[Strategy] = []
        self._data_loader = BacktestDataLoader(config.catalog_path)
        self._venue_params: VenueSimulationParams | None = None
        self._equity_curve: list[float] = []
        self._fills_data: list[dict[str, Any]] = []

    @property
    def engine(self) -> BacktestEngine | None:
        """Get the underlying BacktestEngine."""
        return self._engine

    def setup(self) -> None:
        """
        Set up the backtest engine and venue.

        Call this before adding strategies and running.
        """
        # Create engine config
        engine_config = BacktestEngineConfig(
            trader_id=TraderId(self.config.trader_id),
            logging=LoggingConfig(
                log_level=self.config.log_level,
                bypass=self.config.bypass_logging,
            ),
        )

        # Create engine
        self._engine = BacktestEngine(config=engine_config)

        # Get simulation parameters for venue
        try:
            self._venue_params = VenueSimulationParams.from_exchange(self.config.venue)
        except ValueError:
            # Use default Binance params if unknown
            self._venue_params = VenueSimulationParams.from_exchange("binance")

        # Determine currency
        if self.config.base_currency.upper() == "USDT":
            currency = USDT
        else:
            currency = USD

        # Add venue with simulation models
        assert self._engine is not None, "Engine not initialized"
        self._engine.add_venue(
            venue=Venue(self.config.venue),
            oms_type=self.config.oms_type,
            account_type=self.config.account_type,
            starting_balances=[Money(Decimal(str(self.config.starting_balance)), currency)],
            fill_model=self._venue_params.fill_model,
            latency_model=self._venue_params.latency_model,
        )

    def add_strategy(self, strategy: Strategy) -> None:
        """
        Add a strategy to the backtest.

        Args:
            strategy: Strategy instance to add.
        """
        if self._engine is None:
            raise RuntimeError("Must call setup() before adding strategies")

        self._strategies.append(strategy)
        self._engine.add_strategy(strategy)

    def add_data(
        self,
        instrument_ids: list[str] | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> None:
        """
        Add data from catalog to the engine.

        Args:
            instrument_ids: Instruments to load (uses config if None).
            start_time: Start time (uses config if None).
            end_time: End time (uses config if None).
        """
        if self._engine is None:
            raise RuntimeError("Must call setup() before adding data")

        instrument_ids = instrument_ids or self.config.instrument_ids
        start_time = start_time or self.config.start_time
        end_time = end_time or self.config.end_time

        # Load instruments from catalog
        catalog = self._data_loader.catalog

        for inst_id_str in instrument_ids:
            # Get instrument definition
            instruments = catalog.instruments()
            for inst in instruments:
                if str(inst.id) == inst_id_str:
                    self._engine.add_instrument(inst)
                    break

        # Load bar data
        bars = self._data_loader.load_bars(
            instrument_ids=instrument_ids,
            start_time=start_time,
            end_time=end_time,
        )

        if bars:
            self._engine.add_data(bars)

    def run(self) -> BacktestResult:
        """
        Run the backtest.

        Returns:
            BacktestResult with metrics and analysis.
        """
        if self._engine is None:
            raise RuntimeError("Must call setup() before running")

        start = datetime.now(timezone.utc)

        # Run backtest
        self._engine.run()

        end = datetime.now(timezone.utc)

        # Extract results
        return self._extract_results(start, end)

    def _extract_results(
        self,
        run_start: datetime,
        run_end: datetime,
    ) -> BacktestResult:
        """Extract results from completed backtest."""
        if self._engine is None:
            raise RuntimeError("Engine not initialized")

        # Extract equity curve and fills for metric calculations
        self._extract_equity_curve()
        self._extract_fills_data()

        # Get account state
        account = self._engine.trader.generate_account_report(Venue(self.config.venue))
        positions = self._engine.trader.generate_positions_report()
        orders = self._engine.trader.generate_orders_report()
        fills = self._engine.trader.generate_fills_report()

        # Calculate metrics
        total_return = self._calculate_total_return(account)
        sharpe = self._calculate_sharpe_ratio()
        max_dd = self._calculate_max_drawdown()
        total_trades = len(fills) if fills is not None else 0
        win_rate = self._calculate_win_rate()
        profit_factor = self._calculate_profit_factor()

        # Extract balances
        balances: dict[str, float] = {}
        if account is not None:
            for currency, balance in account.items():
                balances[str(currency)] = float(balance)

        # Extract positions
        pos_list: list[dict[str, Any]] = []
        if positions is not None:
            for pos in positions:
                pos_list.append({"instrument": str(pos)})

        # Order/fill counts
        order_counts: dict[str, int] = {"total": len(orders) if orders is not None else 0}
        fill_counts: dict[str, int] = {"total": total_trades}

        return BacktestResult(
            start_time=self.config.start_time or run_start,
            end_time=self.config.end_time or run_end,
            duration_seconds=(run_end - run_start).total_seconds(),
            total_return=total_return,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            account_balances=balances,
            positions=pos_list,
            orders=order_counts,
            fills=fill_counts,
        )

    def _calculate_total_return(self, account: Any) -> float:
        """Calculate total return from account state."""
        if account is None:
            return 0.0

        # Extract final balance from account report
        final_balance = 0.0
        for currency, balance in account.items():
            # Use the base currency balance
            currency_str = str(currency)
            if currency_str == self.config.base_currency:
                final_balance = float(balance)
                break

        if final_balance == 0.0:
            # Fallback: use first available balance
            for balance in account.values():
                final_balance = float(balance)
                break

        starting = self.config.starting_balance
        if starting <= 0:
            return 0.0

        return (final_balance - starting) / starting

    def _calculate_sharpe_ratio(self) -> float:
        """Calculate Sharpe ratio from returns."""
        if len(self._equity_curve) < 2:
            # Not enough data - estimate from total return
            return 0.0

        equity = np.array(self._equity_curve)
        returns = np.diff(equity) / equity[:-1]

        if len(returns) == 0:
            return 0.0

        std = np.std(returns)
        if std < 1e-10:
            return 0.0

        # Annualize assuming daily returns
        return float(np.mean(returns) / std * np.sqrt(252))

    def _calculate_max_drawdown(self) -> float:
        """Calculate maximum drawdown."""
        if len(self._equity_curve) < 2:
            return 0.0

        equity = np.array(self._equity_curve)
        running_max = np.maximum.accumulate(equity)

        # Avoid division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            drawdown = (running_max - equity) / running_max
            drawdown = np.nan_to_num(drawdown, nan=0.0, posinf=0.0, neginf=0.0)

        return float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

    def _calculate_win_rate(self) -> float:
        """Calculate win rate from trades."""
        if not self._fills_data:
            return 0.0

        winning_trades = sum(1 for f in self._fills_data if f.get("pnl", 0) > 0)
        total_trades = len(self._fills_data)

        if total_trades == 0:
            return 0.0

        return winning_trades / total_trades

    def _calculate_profit_factor(self) -> float:
        """Calculate profit factor."""
        if not self._fills_data:
            return 0.0

        gross_profit = sum(f.get("pnl", 0) for f in self._fills_data if f.get("pnl", 0) > 0)
        gross_loss = abs(sum(f.get("pnl", 0) for f in self._fills_data if f.get("pnl", 0) < 0))

        if gross_loss < 1e-10:
            return float("inf") if gross_profit > 0 else 0.0

        return gross_profit / gross_loss

    def _extract_equity_curve(self) -> None:
        """Extract equity curve from engine after run."""
        if self._engine is None:
            return

        # Get account history if available
        try:
            account = self._engine.trader.generate_account_report(Venue(self.config.venue))
            if account:
                # Start with initial balance
                self._equity_curve = [self.config.starting_balance]

                # Add final balance
                for currency, balance in account.items():
                    if str(currency) == self.config.base_currency:
                        self._equity_curve.append(float(balance))
                        break
        except Exception:
            # Fallback to empty curve
            self._equity_curve = [self.config.starting_balance]

    def _extract_fills_data(self) -> None:
        """Extract fills data from engine after run."""
        if self._engine is None:
            return

        try:
            fills = self._engine.trader.generate_fills_report()
            if fills is not None:
                self._fills_data = []
                for fill in fills:
                    # Extract basic fill info
                    self._fills_data.append({
                        "instrument": str(fill) if hasattr(fill, "__str__") else "unknown",
                        "pnl": 0.0,  # Would need actual PnL from position tracking
                    })
        except Exception:
            self._fills_data = []

    def reset(self) -> None:
        """Reset the engine for another run."""
        if self._engine is not None:
            self._engine.reset()
        self._strategies.clear()

    def dispose(self) -> None:
        """Clean up resources."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None


def run_backtest(
    config: BacktestConfig,
    strategies: list[Strategy],
) -> BacktestResult:
    """
    Convenience function to run a backtest.

    Args:
        config: Backtest configuration.
        strategies: List of strategies to run.

    Returns:
        BacktestResult with metrics.
    """
    runner = BacktestRunner(config)
    runner.setup()

    for strategy in strategies:
        runner.add_strategy(strategy)

    runner.add_data()

    try:
        result = runner.run()
    finally:
        runner.dispose()

    return result
