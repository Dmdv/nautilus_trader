"""
Data wranglers for transforming raw data to NautilusTrader format.

This module provides wranglers for converting raw market data (CSV, DataFrame)
into NautilusTrader data objects (TradeTick, QuoteTick, Bar, OrderBookDelta).

Wranglers:
    - TradeTickWrangler: Process trade/tick data
    - QuoteTickWrangler: Process quote (BBO) data
    - BarDataWrangler: Process OHLCV bar data
    - OrderBookDeltaWrangler: Process order book updates

Example:
    >>> from impl.data.wranglers import TradeTickWrangler
    >>> import pandas as pd
    >>> df = pd.read_csv("trades.csv")
    >>> wrangler = TradeTickWrangler(instrument)
    >>> trade_ticks = wrangler.process(df)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import pandas as pd

logger = logging.getLogger(__name__)


class AggressorSide(str, Enum):
    """Aggressor side for trade ticks."""

    BUY = "BUY"
    SELL = "SELL"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, value: str) -> "AggressorSide":
        """Parse aggressor side from string."""
        value_upper = value.upper().strip()
        if value_upper in ("BUY", "B", "1", "TRUE"):
            return cls.BUY
        elif value_upper in ("SELL", "S", "0", "FALSE"):
            return cls.SELL
        return cls.UNKNOWN


@dataclass
class WranglerConfig:
    """
    Configuration for data wranglers.

    Attributes:
        timestamp_column: Column name for timestamp.
        timestamp_unit: Unit of timestamp (s, ms, us, ns).
        timestamp_format: Format string for parsing string timestamps.
        price_precision: Price decimal precision.
        size_precision: Size decimal precision.
        drop_invalid: Drop rows with invalid data.
        fill_missing: Fill missing values.
    """

    timestamp_column: str = "timestamp"
    timestamp_unit: str = "ns"
    timestamp_format: str | None = None
    price_precision: int = 8
    size_precision: int = 8
    drop_invalid: bool = True
    fill_missing: bool = False


@runtime_checkable
class InstrumentProtocol(Protocol):
    """Protocol for instrument objects."""

    @property
    def id(self) -> Any:
        """Get instrument ID."""
        ...

    @property
    def price_precision(self) -> int:
        """Get price precision."""
        ...

    @property
    def size_precision(self) -> int:
        """Get size precision."""
        ...


@dataclass
class MockInstrument:
    """
    Mock instrument for testing and development.

    Use this when NautilusTrader instrument is not available.
    """

    instrument_id: str
    price_precision: int = 2
    size_precision: int = 3
    raw_symbol: str = ""

    @property
    def id(self) -> str:
        """Get instrument ID string."""
        return self.instrument_id

    @classmethod
    def from_string(
        cls,
        instrument_id: str,
        price_precision: int = 2,
        size_precision: int = 3,
    ) -> "MockInstrument":
        """Create from instrument ID string."""
        raw_symbol = instrument_id.split(".")[0].replace("-PERP", "")
        return cls(
            instrument_id=instrument_id,
            price_precision=price_precision,
            size_precision=size_precision,
            raw_symbol=raw_symbol,
        )


@dataclass
class TradeTick:
    """
    Trade tick data object.

    Represents a single executed trade.
    """

    instrument_id: str
    price: Decimal
    size: Decimal
    aggressor_side: AggressorSide
    trade_id: str
    ts_event: int  # Nanoseconds
    ts_init: int  # Nanoseconds

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "instrument_id": self.instrument_id,
            "price": str(self.price),
            "size": str(self.size),
            "aggressor_side": self.aggressor_side.value,
            "trade_id": self.trade_id,
            "ts_event": self.ts_event,
            "ts_init": self.ts_init,
        }


@dataclass
class QuoteTick:
    """
    Quote tick data object.

    Represents best bid/ask at a point in time.
    """

    instrument_id: str
    bid_price: Decimal
    ask_price: Decimal
    bid_size: Decimal
    ask_size: Decimal
    ts_event: int  # Nanoseconds
    ts_init: int  # Nanoseconds

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "instrument_id": self.instrument_id,
            "bid_price": str(self.bid_price),
            "ask_price": str(self.ask_price),
            "bid_size": str(self.bid_size),
            "ask_size": str(self.ask_size),
            "ts_event": self.ts_event,
            "ts_init": self.ts_init,
        }


@dataclass
class Bar:
    """
    OHLCV bar data object.

    Represents aggregated price data over a time period.
    """

    bar_type: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    ts_event: int  # Nanoseconds (bar close time)
    ts_init: int  # Nanoseconds

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bar_type": self.bar_type,
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume),
            "ts_event": self.ts_event,
            "ts_init": self.ts_init,
        }


@dataclass
class OrderBookDelta:
    """
    Order book delta/update object.

    Represents a change to the order book state.
    """

    instrument_id: str
    action: str  # ADD, UPDATE, DELETE, CLEAR
    side: str  # BID, ASK
    price: Decimal
    size: Decimal
    ts_event: int  # Nanoseconds
    ts_init: int  # Nanoseconds
    sequence: int = 0

    def as_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "instrument_id": self.instrument_id,
            "action": self.action,
            "side": self.side,
            "price": str(self.price),
            "size": str(self.size),
            "ts_event": self.ts_event,
            "ts_init": self.ts_init,
            "sequence": self.sequence,
        }


class BaseWrangler:
    """
    Base class for data wranglers.

    Provides common functionality for parsing timestamps and
    validating data.
    """

    def __init__(
        self,
        instrument: InstrumentProtocol | MockInstrument,
        config: WranglerConfig | None = None,
    ) -> None:
        """
        Initialize the wrangler.

        Args:
            instrument: Instrument definition.
            config: Wrangler configuration.
        """
        self.instrument = instrument
        self.config = config or WranglerConfig()

    def _parse_timestamp(self, value: Any) -> int:
        """
        Parse timestamp to nanoseconds.

        Args:
            value: Timestamp value (int, float, or string).

        Returns:
            Timestamp in nanoseconds.
        """
        if isinstance(value, (int, float)):
            # Assume it's already in the configured unit
            if self.config.timestamp_unit == "s":
                return int(value * 1_000_000_000)
            elif self.config.timestamp_unit == "ms":
                return int(value * 1_000_000)
            elif self.config.timestamp_unit == "us":
                return int(value * 1_000)
            else:  # ns
                return int(value)
        elif isinstance(value, str):
            if self.config.timestamp_format:
                dt = datetime.strptime(value, self.config.timestamp_format)
            else:
                dt = pd.to_datetime(value)
            return int(dt.timestamp() * 1_000_000_000)
        elif isinstance(value, pd.Timestamp):
            return int(value.timestamp() * 1_000_000_000)
        else:
            raise ValueError(f"Cannot parse timestamp: {value} ({type(value)})")

    def _parse_decimal(self, value: Any, precision: int) -> Decimal:
        """
        Parse value to Decimal with precision.

        Args:
            value: Numeric value.
            precision: Decimal precision.

        Returns:
            Decimal value.
        """
        if pd.isna(value):
            return Decimal("0")
        return Decimal(str(value)).quantize(
            Decimal(10) ** -precision
        )

    def _validate_dataframe(self, df: pd.DataFrame, required_columns: list[str]) -> None:
        """
        Validate DataFrame has required columns.

        Args:
            df: DataFrame to validate.
            required_columns: List of required column names.

        Raises:
            ValueError: If required columns are missing.
        """
        missing = set(required_columns) - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")


class TradeTickWrangler(BaseWrangler):
    """
    Wrangler for trade tick data.

    Transforms raw trade data (CSV/DataFrame) into TradeTick objects
    compatible with NautilusTrader.

    Expected columns:
        - timestamp: Trade timestamp
        - price: Trade price
        - size/amount/quantity: Trade size
        - side/aggressor_side: Buy or Sell
        - trade_id (optional): Trade identifier

    Example:
        >>> wrangler = TradeTickWrangler(instrument)
        >>> df = pd.read_csv("trades.csv")
        >>> ticks = wrangler.process(df)
    """

    # Column name mappings for different data sources
    COLUMN_MAPPINGS = {
        "timestamp": ["timestamp", "ts_event", "time", "datetime", "ts"],
        "price": ["price", "trade_price", "px"],
        "size": ["size", "amount", "quantity", "qty", "volume", "vol"],
        "side": ["side", "aggressor_side", "taker_side", "direction"],
        "trade_id": ["trade_id", "id", "tid"],
    }

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize column names to expected format.

        Args:
            df: Input DataFrame.

        Returns:
            DataFrame with normalized column names.
        """
        df = df.copy()
        column_map = {}

        for target, sources in self.COLUMN_MAPPINGS.items():
            for source in sources:
                if source in df.columns and target not in df.columns:
                    column_map[source] = target
                    break

        return df.rename(columns=column_map)

    def process(
        self,
        data: pd.DataFrame | Path | str,
        **kwargs: Any,
    ) -> list[TradeTick]:
        """
        Process trade data into TradeTick objects.

        Args:
            data: DataFrame, file path, or CSV string.
            **kwargs: Additional options passed to pd.read_csv.

        Returns:
            List of TradeTick objects.
        """
        # Load data
        if isinstance(data, (str, Path)):
            path = Path(data)
            if path.suffix == ".gz":
                df = pd.read_csv(path, compression="gzip", **kwargs)
            else:
                df = pd.read_csv(path, **kwargs)
        else:
            df = data.copy()

        # Normalize columns
        df = self._normalize_columns(df)

        # Validate
        self._validate_dataframe(df, ["timestamp", "price", "size"])

        ticks: list[TradeTick] = []
        instrument_id = str(self.instrument.id)
        price_precision = getattr(self.instrument, "price_precision", 8)
        size_precision = getattr(self.instrument, "size_precision", 8)

        # Use itertuples for better performance (10-100x faster than iterrows)
        for row in df.itertuples(index=True):
            idx = row.Index
            try:
                ts_event = self._parse_timestamp(row.timestamp)

                # Parse side
                side = AggressorSide.UNKNOWN
                if hasattr(row, "side") and row.side:
                    side = AggressorSide.from_string(str(row.side))

                # Parse trade_id
                trade_id = str(getattr(row, "trade_id", idx))

                tick = TradeTick(
                    instrument_id=instrument_id,
                    price=self._parse_decimal(row.price, price_precision),
                    size=self._parse_decimal(row.size, size_precision),
                    aggressor_side=side,
                    trade_id=trade_id,
                    ts_event=ts_event,
                    ts_init=ts_event,
                )
                ticks.append(tick)

            except Exception as e:
                if self.config.drop_invalid:
                    logger.warning("Skipping invalid row %s: %s", idx, e)
                else:
                    raise

        logger.info("Processed %d trade ticks", len(ticks))
        return ticks

    def process_tardis_csv(
        self,
        file_path: Path | str,
    ) -> list[TradeTick]:
        """
        Process a Tardis trades CSV file.

        Tardis trade files have columns:
        timestamp, symbol, side, price, amount, ...

        Args:
            file_path: Path to Tardis CSV file.

        Returns:
            List of TradeTick objects.
        """
        # Tardis uses microseconds for timestamps
        original_unit = self.config.timestamp_unit
        self.config.timestamp_unit = "us"

        try:
            return self.process(file_path)
        finally:
            self.config.timestamp_unit = original_unit


class QuoteTickWrangler(BaseWrangler):
    """
    Wrangler for quote tick (BBO) data.

    Transforms raw quote data into QuoteTick objects.

    Expected columns:
        - timestamp: Quote timestamp
        - bid_price: Best bid price
        - ask_price: Best ask price
        - bid_size: Best bid size
        - ask_size: Best ask size
    """

    COLUMN_MAPPINGS = {
        "timestamp": ["timestamp", "ts_event", "time", "datetime"],
        "bid_price": ["bid_price", "bid", "best_bid", "bid_px"],
        "ask_price": ["ask_price", "ask", "best_ask", "ask_px"],
        "bid_size": ["bid_size", "bid_qty", "bid_amount", "bid_vol"],
        "ask_size": ["ask_size", "ask_qty", "ask_amount", "ask_vol"],
    }

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names."""
        df = df.copy()
        column_map = {}

        for target, sources in self.COLUMN_MAPPINGS.items():
            for source in sources:
                if source in df.columns and target not in df.columns:
                    column_map[source] = target
                    break

        return df.rename(columns=column_map)

    def process(
        self,
        data: pd.DataFrame | Path | str,
        **kwargs: Any,
    ) -> list[QuoteTick]:
        """
        Process quote data into QuoteTick objects.

        Args:
            data: DataFrame, file path, or CSV string.
            **kwargs: Additional options passed to pd.read_csv.

        Returns:
            List of QuoteTick objects.
        """
        # Load data
        if isinstance(data, (str, Path)):
            path = Path(data)
            if path.suffix == ".gz":
                df = pd.read_csv(path, compression="gzip", **kwargs)
            else:
                df = pd.read_csv(path, **kwargs)
        else:
            df = data.copy()

        # Normalize columns
        df = self._normalize_columns(df)

        # Validate
        self._validate_dataframe(
            df, ["timestamp", "bid_price", "ask_price", "bid_size", "ask_size"]
        )

        ticks: list[QuoteTick] = []
        instrument_id = str(self.instrument.id)
        price_precision = getattr(self.instrument, "price_precision", 8)
        size_precision = getattr(self.instrument, "size_precision", 8)

        # Use itertuples for better performance (10-100x faster than iterrows)
        for row in df.itertuples(index=True):
            idx = row.Index
            try:
                ts_event = self._parse_timestamp(row.timestamp)

                tick = QuoteTick(
                    instrument_id=instrument_id,
                    bid_price=self._parse_decimal(row.bid_price, price_precision),
                    ask_price=self._parse_decimal(row.ask_price, price_precision),
                    bid_size=self._parse_decimal(row.bid_size, size_precision),
                    ask_size=self._parse_decimal(row.ask_size, size_precision),
                    ts_event=ts_event,
                    ts_init=ts_event,
                )
                ticks.append(tick)

            except Exception as e:
                if self.config.drop_invalid:
                    logger.warning("Skipping invalid row %s: %s", idx, e)
                else:
                    raise

        logger.info("Processed %d quote ticks", len(ticks))
        return ticks


class BarDataWrangler(BaseWrangler):
    """
    Wrangler for OHLCV bar data.

    Transforms raw bar data into Bar objects.

    Expected columns:
        - timestamp: Bar close timestamp
        - open: Open price
        - high: High price
        - low: Low price
        - close: Close price
        - volume: Volume
    """

    COLUMN_MAPPINGS = {
        "timestamp": ["timestamp", "ts_event", "time", "datetime", "close_time"],
        "open": ["open", "o", "open_price"],
        "high": ["high", "h", "high_price"],
        "low": ["low", "l", "low_price"],
        "close": ["close", "c", "close_price"],
        "volume": ["volume", "vol", "v", "qty"],
    }

    def __init__(
        self,
        bar_type: str,
        instrument: InstrumentProtocol | MockInstrument,
        config: WranglerConfig | None = None,
    ) -> None:
        """
        Initialize the bar wrangler.

        Args:
            bar_type: NautilusTrader bar type string
                (e.g., "BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL").
            instrument: Instrument definition.
            config: Wrangler configuration.
        """
        super().__init__(instrument, config)
        self.bar_type = bar_type

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names."""
        df = df.copy()
        column_map = {}

        for target, sources in self.COLUMN_MAPPINGS.items():
            for source in sources:
                if source in df.columns and target not in df.columns:
                    column_map[source] = target
                    break

        return df.rename(columns=column_map)

    def process(
        self,
        data: pd.DataFrame | Path | str,
        **kwargs: Any,
    ) -> list[Bar]:
        """
        Process bar data into Bar objects.

        Args:
            data: DataFrame, file path, or CSV string.
            **kwargs: Additional options passed to pd.read_csv.

        Returns:
            List of Bar objects.
        """
        # Load data
        if isinstance(data, (str, Path)):
            path = Path(data)
            if path.suffix == ".gz":
                df = pd.read_csv(path, compression="gzip", **kwargs)
            elif path.suffix == ".parquet":
                df = pd.read_parquet(path)
            else:
                df = pd.read_csv(path, **kwargs)
        else:
            df = data.copy()

        # Normalize columns
        df = self._normalize_columns(df)

        # Validate
        self._validate_dataframe(
            df, ["timestamp", "open", "high", "low", "close", "volume"]
        )

        bars: list[Bar] = []
        price_precision = getattr(self.instrument, "price_precision", 8)
        size_precision = getattr(self.instrument, "size_precision", 8)

        # Use itertuples for better performance (10-100x faster than iterrows)
        for row in df.itertuples(index=True):
            idx = row.Index
            try:
                ts_event = self._parse_timestamp(row.timestamp)

                bar = Bar(
                    bar_type=self.bar_type,
                    open=self._parse_decimal(row.open, price_precision),
                    high=self._parse_decimal(row.high, price_precision),
                    low=self._parse_decimal(row.low, price_precision),
                    close=self._parse_decimal(row.close, price_precision),
                    volume=self._parse_decimal(row.volume, size_precision),
                    ts_event=ts_event,
                    ts_init=ts_event,
                )
                bars.append(bar)

            except Exception as e:
                if self.config.drop_invalid:
                    logger.warning("Skipping invalid row %s: %s", idx, e)
                else:
                    raise

        logger.info("Processed %d bars", len(bars))
        return bars


class OrderBookDeltaWrangler(BaseWrangler):
    """
    Wrangler for order book delta/update data.

    Transforms raw order book update data into OrderBookDelta objects.

    Expected columns:
        - timestamp: Update timestamp
        - side: BID or ASK
        - price: Price level
        - size: Size at price level (0 = remove)
    """

    COLUMN_MAPPINGS = {
        "timestamp": ["timestamp", "ts_event", "time", "datetime"],
        "side": ["side", "type"],
        "price": ["price", "px"],
        "size": ["size", "amount", "qty", "quantity"],
        "action": ["action", "type"],
    }

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize column names."""
        df = df.copy()
        column_map = {}

        for target, sources in self.COLUMN_MAPPINGS.items():
            for source in sources:
                if source in df.columns and target not in df.columns:
                    column_map[source] = target
                    break

        return df.rename(columns=column_map)

    def _parse_side(self, value: str) -> str:
        """Parse order book side."""
        value_upper = str(value).upper()
        if value_upper in ("BID", "BIDS", "B", "BUY"):
            return "BID"
        elif value_upper in ("ASK", "ASKS", "A", "SELL"):
            return "ASK"
        return "UNKNOWN"

    def _parse_action(self, size: Decimal, action: str | None = None) -> str:
        """Determine action based on size or explicit action."""
        if action:
            action_upper = action.upper()
            if action_upper in ("ADD", "INSERT"):
                return "ADD"
            elif action_upper in ("DELETE", "REMOVE"):
                return "DELETE"
            elif action_upper in ("UPDATE", "CHANGE"):
                return "UPDATE"
            elif action_upper == "CLEAR":
                return "CLEAR"

        # Infer from size
        if size == Decimal("0"):
            return "DELETE"
        return "UPDATE"

    def process(
        self,
        data: pd.DataFrame | Path | str,
        **kwargs: Any,
    ) -> list[OrderBookDelta]:
        """
        Process order book data into OrderBookDelta objects.

        Args:
            data: DataFrame, file path, or CSV string.
            **kwargs: Additional options passed to pd.read_csv.

        Returns:
            List of OrderBookDelta objects.
        """
        # Load data
        if isinstance(data, (str, Path)):
            path = Path(data)
            if path.suffix == ".gz":
                df = pd.read_csv(path, compression="gzip", **kwargs)
            else:
                df = pd.read_csv(path, **kwargs)
        else:
            df = data.copy()

        # Normalize columns
        df = self._normalize_columns(df)

        # Validate
        self._validate_dataframe(df, ["timestamp", "side", "price", "size"])

        deltas: list[OrderBookDelta] = []
        instrument_id = str(self.instrument.id)
        price_precision = getattr(self.instrument, "price_precision", 8)
        size_precision = getattr(self.instrument, "size_precision", 8)

        # Use itertuples for better performance (10-100x faster than iterrows)
        for row in df.itertuples(index=True):
            idx = row.Index
            try:
                ts_event = self._parse_timestamp(row.timestamp)
                size = self._parse_decimal(row.size, size_precision)
                action_val = getattr(row, "action", None)
                action = self._parse_action(size, action_val)

                delta = OrderBookDelta(
                    instrument_id=instrument_id,
                    action=action,
                    side=self._parse_side(row.side),
                    price=self._parse_decimal(row.price, price_precision),
                    size=size,
                    ts_event=ts_event,
                    ts_init=ts_event,
                    sequence=int(getattr(row, "sequence", idx)),
                )
                deltas.append(delta)

            except Exception as e:
                if self.config.drop_invalid:
                    logger.warning("Skipping invalid row %s: %s", idx, e)
                else:
                    raise

        logger.info("Processed %d order book deltas", len(deltas))
        return deltas


def aggregate_trades_to_bars(
    trades: list[TradeTick],
    bar_period_ns: int = 60_000_000_000,  # 1 minute in nanoseconds
) -> list[Bar]:
    """
    Aggregate trade ticks into OHLCV bars.

    Args:
        trades: List of TradeTick objects (must be sorted by time).
        bar_period_ns: Bar period in nanoseconds.

    Returns:
        List of Bar objects.
    """
    if not trades:
        return []

    bars: list[Bar] = []
    current_bar_start = (trades[0].ts_event // bar_period_ns) * bar_period_ns

    open_price = trades[0].price
    high_price = trades[0].price
    low_price = trades[0].price
    close_price = trades[0].price
    volume = Decimal("0")

    for trade in trades:
        bar_start = (trade.ts_event // bar_period_ns) * bar_period_ns

        if bar_start != current_bar_start:
            # Save current bar
            bars.append(Bar(
                bar_type="",  # Will be set by caller
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume,
                ts_event=current_bar_start + bar_period_ns,
                ts_init=current_bar_start + bar_period_ns,
            ))

            # Reset for new bar
            current_bar_start = bar_start
            open_price = trade.price
            high_price = trade.price
            low_price = trade.price
            volume = Decimal("0")

        # Update current bar
        high_price = max(high_price, trade.price)
        low_price = min(low_price, trade.price)
        close_price = trade.price
        volume += trade.size

    # Save final bar
    if volume > 0:
        bars.append(Bar(
            bar_type="",
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            ts_event=current_bar_start + bar_period_ns,
            ts_init=current_bar_start + bar_period_ns,
        ))

    return bars
