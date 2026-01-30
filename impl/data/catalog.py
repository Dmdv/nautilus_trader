"""
Parquet catalog management for NautilusTrader data.

This module provides a catalog manager for storing and retrieving
market data in Parquet format with automatic partitioning by
venue, instrument, year, and month.

Catalog Structure:
    data/catalog/
    |-- trade_tick/
    |   |-- BTCUSDT-PERP.BINANCE/
    |   |   |-- 2024/
    |   |   |   |-- 01/
    |   |   |   |   |-- data.parquet
    |   |   |   |-- 02/
    |   |   |   |   |-- data.parquet
    |-- bar_1m/
    |   |-- ETHUSDT-PERP.BINANCE/
    |   |   |-- 2024/01/data.parquet
    |-- quote_tick/
    |-- order_book_delta/

Example:
    >>> from impl.data.catalog import ParquetCatalogManager
    >>> catalog = ParquetCatalogManager("data/catalog")
    >>> # Write data
    >>> catalog.write_trade_ticks(trade_ticks)
    >>> # Read data
    >>> ticks = catalog.read_trade_ticks("BTCUSDT-PERP.BINANCE", "2024-01-01", "2024-01-31")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .wranglers import Bar, OrderBookDelta, QuoteTick, TradeTick

logger = logging.getLogger(__name__)

# Type variable for data types
DataT = TypeVar("DataT", TradeTick, QuoteTick, Bar, OrderBookDelta)


@dataclass
class DataGap:
    """
    Represents a gap in data coverage.

    Attributes:
        start_ts: Start of gap in nanoseconds.
        end_ts: End of gap in nanoseconds.
        missing_count: Estimated number of missing records.
        gap_type: Type of gap (time_gap, missing_date, etc.).
    """

    start_ts: int
    end_ts: int
    missing_count: int
    gap_type: str = "time_gap"

    @property
    def duration_seconds(self) -> float:
        """Get gap duration in seconds."""
        return (self.end_ts - self.start_ts) / 1_000_000_000

    @property
    def start_datetime(self) -> datetime:
        """Get start as datetime."""
        return datetime.fromtimestamp(self.start_ts / 1_000_000_000)

    @property
    def end_datetime(self) -> datetime:
        """Get end as datetime."""
        return datetime.fromtimestamp(self.end_ts / 1_000_000_000)


@dataclass
class ValidationResult:
    """
    Result of data validation.

    Attributes:
        is_valid: Whether data passed validation.
        total_records: Total number of records checked.
        issues: List of validation issues found.
        gaps: List of data gaps found.
        statistics: Additional statistics.
    """

    is_valid: bool
    total_records: int
    issues: list[str]
    gaps: list[DataGap]
    statistics: dict[str, Any] = field(default_factory=dict)


@dataclass
class CatalogQueryResult:
    """
    Result of a catalog query.

    Attributes:
        data: List of data objects.
        instrument_id: Instrument ID queried.
        start_date: Query start date.
        end_date: Query end date.
        record_count: Number of records returned.
        files_read: List of files read.
    """

    data: list[Any]
    instrument_id: str
    start_date: str
    end_date: str
    record_count: int
    files_read: list[Path]


@dataclass
class CatalogInfo:
    """
    Information about catalog contents.

    Attributes:
        path: Catalog root path.
        data_types: Available data types.
        instruments: Available instruments by data type.
        date_ranges: Date ranges by instrument.
        total_size_bytes: Total size of catalog.
    """

    path: Path
    data_types: list[str]
    instruments: dict[str, list[str]]
    date_ranges: dict[str, dict[str, tuple[str, str]]]
    total_size_bytes: int

    @property
    def total_size_mb(self) -> float:
        """Get total size in MB."""
        return self.total_size_bytes / (1024 * 1024)


class ParquetCatalogManager:
    """
    Manager for Parquet data catalog.

    Provides methods for writing, reading, and querying market data
    stored in Parquet format with automatic partitioning.

    Example:
        >>> catalog = ParquetCatalogManager("data/catalog")
        >>> catalog.write_trade_ticks(trade_ticks)
        >>> ticks = catalog.read_trade_ticks(
        ...     "BTCUSDT-PERP.BINANCE",
        ...     "2024-01-01",
        ...     "2024-01-31"
        ... )
    """

    # Data type directory names
    DATA_TYPE_DIRS = {
        "trade_tick": "trade_tick",
        "quote_tick": "quote_tick",
        "bar": "bar",
        "order_book_delta": "order_book_delta",
    }

    def __init__(self, catalog_path: Path | str) -> None:
        """
        Initialize the catalog manager.

        Args:
            catalog_path: Root path for the catalog.
        """
        self.catalog_path = Path(catalog_path)
        self.catalog_path.mkdir(parents=True, exist_ok=True)

    def _get_partition_path(
        self,
        data_type: str,
        instrument_id: str,
        year: int,
        month: int,
    ) -> Path:
        """
        Get path for a data partition.

        Args:
            data_type: Type of data (trade_tick, bar, etc.).
            instrument_id: Instrument ID.
            year: Year.
            month: Month.

        Returns:
            Path to the partition directory.
        """
        # Sanitize instrument_id for filesystem
        safe_instrument = instrument_id.replace("/", "_").replace(":", "_")
        return (
            self.catalog_path
            / data_type
            / safe_instrument
            / str(year)
            / f"{month:02d}"
        )

    def _get_parquet_path(
        self,
        data_type: str,
        instrument_id: str,
        year: int,
        month: int,
    ) -> Path:
        """Get path to parquet file."""
        return self._get_partition_path(data_type, instrument_id, year, month) / "data.parquet"

    def _ts_to_partition(self, ts_ns: int) -> tuple[int, int]:
        """
        Convert timestamp to year/month partition.

        Args:
            ts_ns: Timestamp in nanoseconds.

        Returns:
            Tuple of (year, month).
        """
        dt = datetime.fromtimestamp(ts_ns / 1_000_000_000)
        return dt.year, dt.month

    def _trade_ticks_to_df(self, ticks: list[TradeTick]) -> pd.DataFrame:
        """Convert trade ticks to DataFrame."""
        return pd.DataFrame([t.as_dict() for t in ticks])

    def _quote_ticks_to_df(self, ticks: list[QuoteTick]) -> pd.DataFrame:
        """Convert quote ticks to DataFrame."""
        return pd.DataFrame([t.as_dict() for t in ticks])

    def _bars_to_df(self, bars: list[Bar]) -> pd.DataFrame:
        """Convert bars to DataFrame."""
        return pd.DataFrame([b.as_dict() for b in bars])

    def _deltas_to_df(self, deltas: list[OrderBookDelta]) -> pd.DataFrame:
        """Convert order book deltas to DataFrame."""
        return pd.DataFrame([d.as_dict() for d in deltas])

    def _df_to_trade_ticks(self, df: pd.DataFrame) -> list[TradeTick]:
        """Convert DataFrame to trade ticks."""
        from decimal import Decimal
        from .wranglers import AggressorSide

        ticks = []
        for _, row in df.iterrows():
            ticks.append(TradeTick(
                instrument_id=row["instrument_id"],
                price=Decimal(str(row["price"])),
                size=Decimal(str(row["size"])),
                aggressor_side=AggressorSide(row["aggressor_side"]),
                trade_id=row["trade_id"],
                ts_event=int(row["ts_event"]),
                ts_init=int(row["ts_init"]),
            ))
        return ticks

    def _df_to_quote_ticks(self, df: pd.DataFrame) -> list[QuoteTick]:
        """Convert DataFrame to quote ticks."""
        from decimal import Decimal

        ticks = []
        for _, row in df.iterrows():
            ticks.append(QuoteTick(
                instrument_id=row["instrument_id"],
                bid_price=Decimal(str(row["bid_price"])),
                ask_price=Decimal(str(row["ask_price"])),
                bid_size=Decimal(str(row["bid_size"])),
                ask_size=Decimal(str(row["ask_size"])),
                ts_event=int(row["ts_event"]),
                ts_init=int(row["ts_init"]),
            ))
        return ticks

    def _df_to_bars(self, df: pd.DataFrame) -> list[Bar]:
        """Convert DataFrame to bars."""
        from decimal import Decimal

        bars = []
        for _, row in df.iterrows():
            bars.append(Bar(
                bar_type=row["bar_type"],
                open=Decimal(str(row["open"])),
                high=Decimal(str(row["high"])),
                low=Decimal(str(row["low"])),
                close=Decimal(str(row["close"])),
                volume=Decimal(str(row["volume"])),
                ts_event=int(row["ts_event"]),
                ts_init=int(row["ts_init"]),
            ))
        return bars

    def _df_to_deltas(self, df: pd.DataFrame) -> list[OrderBookDelta]:
        """Convert DataFrame to order book deltas."""
        from decimal import Decimal

        deltas = []
        for _, row in df.iterrows():
            deltas.append(OrderBookDelta(
                instrument_id=row["instrument_id"],
                action=row["action"],
                side=row["side"],
                price=Decimal(str(row["price"])),
                size=Decimal(str(row["size"])),
                ts_event=int(row["ts_event"]),
                ts_init=int(row["ts_init"]),
                sequence=int(row.get("sequence", 0)),
            ))
        return deltas

    def write_trade_ticks(
        self,
        ticks: list[TradeTick],
        append: bool = True,
    ) -> list[Path]:
        """
        Write trade ticks to catalog.

        Args:
            ticks: List of TradeTick objects.
            append: If True, append to existing data.

        Returns:
            List of files written.
        """
        if not ticks:
            return []

        # Group by partition
        partitions: dict[tuple[int, int], list[TradeTick]] = {}
        instrument_id = ticks[0].instrument_id

        for tick in ticks:
            key = self._ts_to_partition(tick.ts_event)
            if key not in partitions:
                partitions[key] = []
            partitions[key].append(tick)

        written_files: list[Path] = []

        for (year, month), partition_ticks in partitions.items():
            file_path = self._get_parquet_path("trade_tick", instrument_id, year, month)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            df = self._trade_ticks_to_df(partition_ticks)

            if append and file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=["ts_event", "trade_id"])
                df = df.sort_values("ts_event")

            df.to_parquet(file_path, index=False)
            written_files.append(file_path)
            logger.info("Wrote %d trade ticks to %s", len(partition_ticks), file_path)

        return written_files

    def write_quote_ticks(
        self,
        ticks: list[QuoteTick],
        append: bool = True,
    ) -> list[Path]:
        """
        Write quote ticks to catalog.

        Args:
            ticks: List of QuoteTick objects.
            append: If True, append to existing data.

        Returns:
            List of files written.
        """
        if not ticks:
            return []

        partitions: dict[tuple[int, int], list[QuoteTick]] = {}
        instrument_id = ticks[0].instrument_id

        for tick in ticks:
            key = self._ts_to_partition(tick.ts_event)
            if key not in partitions:
                partitions[key] = []
            partitions[key].append(tick)

        written_files: list[Path] = []

        for (year, month), partition_ticks in partitions.items():
            file_path = self._get_parquet_path("quote_tick", instrument_id, year, month)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            df = self._quote_ticks_to_df(partition_ticks)

            if append and file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=["ts_event"])
                df = df.sort_values("ts_event")

            df.to_parquet(file_path, index=False)
            written_files.append(file_path)

        return written_files

    def write_bars(
        self,
        bars: list[Bar],
        bar_period: str = "1m",
        append: bool = True,
    ) -> list[Path]:
        """
        Write bars to catalog.

        Args:
            bars: List of Bar objects.
            bar_period: Bar period (1m, 5m, 1h, etc.).
            append: If True, append to existing data.

        Returns:
            List of files written.
        """
        if not bars:
            return []

        # Extract instrument from bar_type
        bar_type = bars[0].bar_type
        parts = bar_type.split("-")
        instrument_id = parts[0] if "." in parts[0] else f"{parts[0]}.{parts[1]}" if len(parts) > 1 else bar_type

        partitions: dict[tuple[int, int], list[Bar]] = {}

        for bar in bars:
            key = self._ts_to_partition(bar.ts_event)
            if key not in partitions:
                partitions[key] = []
            partitions[key].append(bar)

        written_files: list[Path] = []
        data_type_dir = f"bar_{bar_period}"

        for (year, month), partition_bars in partitions.items():
            file_path = self._get_parquet_path(data_type_dir, instrument_id, year, month)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            df = self._bars_to_df(partition_bars)

            if append and file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.drop_duplicates(subset=["ts_event"])
                df = df.sort_values("ts_event")

            df.to_parquet(file_path, index=False)
            written_files.append(file_path)

        return written_files

    def write_order_book_deltas(
        self,
        deltas: list[OrderBookDelta],
        append: bool = True,
    ) -> list[Path]:
        """
        Write order book deltas to catalog.

        Args:
            deltas: List of OrderBookDelta objects.
            append: If True, append to existing data.

        Returns:
            List of files written.
        """
        if not deltas:
            return []

        partitions: dict[tuple[int, int], list[OrderBookDelta]] = {}
        instrument_id = deltas[0].instrument_id

        for delta in deltas:
            key = self._ts_to_partition(delta.ts_event)
            if key not in partitions:
                partitions[key] = []
            partitions[key].append(delta)

        written_files: list[Path] = []

        for (year, month), partition_deltas in partitions.items():
            file_path = self._get_parquet_path("order_book_delta", instrument_id, year, month)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            df = self._deltas_to_df(partition_deltas)

            if append and file_path.exists():
                existing_df = pd.read_parquet(file_path)
                df = pd.concat([existing_df, df], ignore_index=True)
                df = df.sort_values("ts_event")

            df.to_parquet(file_path, index=False)
            written_files.append(file_path)

        return written_files

    def read_trade_ticks(
        self,
        instrument_id: str,
        start_date: str,
        end_date: str,
    ) -> CatalogQueryResult:
        """
        Read trade ticks from catalog.

        Args:
            instrument_id: Instrument ID to query.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            CatalogQueryResult with trade ticks.
        """
        return self._read_data(
            "trade_tick",
            instrument_id,
            start_date,
            end_date,
            self._df_to_trade_ticks,
        )

    def read_quote_ticks(
        self,
        instrument_id: str,
        start_date: str,
        end_date: str,
    ) -> CatalogQueryResult:
        """
        Read quote ticks from catalog.

        Args:
            instrument_id: Instrument ID to query.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            CatalogQueryResult with quote ticks.
        """
        return self._read_data(
            "quote_tick",
            instrument_id,
            start_date,
            end_date,
            self._df_to_quote_ticks,
        )

    def read_bars(
        self,
        instrument_id: str,
        start_date: str,
        end_date: str,
        bar_period: str = "1m",
    ) -> CatalogQueryResult:
        """
        Read bars from catalog.

        Args:
            instrument_id: Instrument ID to query.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            bar_period: Bar period (1m, 5m, 1h, etc.).

        Returns:
            CatalogQueryResult with bars.
        """
        return self._read_data(
            f"bar_{bar_period}",
            instrument_id,
            start_date,
            end_date,
            self._df_to_bars,
        )

    def read_order_book_deltas(
        self,
        instrument_id: str,
        start_date: str,
        end_date: str,
    ) -> CatalogQueryResult:
        """
        Read order book deltas from catalog.

        Args:
            instrument_id: Instrument ID to query.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).

        Returns:
            CatalogQueryResult with order book deltas.
        """
        return self._read_data(
            "order_book_delta",
            instrument_id,
            start_date,
            end_date,
            self._df_to_deltas,
        )

    def _read_data(
        self,
        data_type: str,
        instrument_id: str,
        start_date: str,
        end_date: str,
        converter: Any,
    ) -> CatalogQueryResult:
        """
        Generic data reading method.

        Args:
            data_type: Data type directory.
            instrument_id: Instrument ID.
            start_date: Start date.
            end_date: End date.
            converter: Function to convert DataFrame to data objects.

        Returns:
            CatalogQueryResult.
        """
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        start_ns = int(start.timestamp() * 1_000_000_000)
        end_ns = int(end.timestamp() * 1_000_000_000) + 86400_000_000_000  # Include end day

        files_to_read: list[Path] = []
        safe_instrument = instrument_id.replace("/", "_").replace(":", "_")
        instrument_dir = self.catalog_path / data_type / safe_instrument

        if not instrument_dir.exists():
            return CatalogQueryResult(
                data=[],
                instrument_id=instrument_id,
                start_date=start_date,
                end_date=end_date,
                record_count=0,
                files_read=[],
            )

        # Find relevant partition files
        current = start
        while current <= end:
            year, month = current.year, current.month
            file_path = self._get_parquet_path(data_type, instrument_id, year, month)
            if file_path.exists():
                files_to_read.append(file_path)

            # Move to next month
            if month == 12:
                current = current.replace(year=year + 1, month=1)
            else:
                current = current.replace(month=month + 1)

        if not files_to_read:
            return CatalogQueryResult(
                data=[],
                instrument_id=instrument_id,
                start_date=start_date,
                end_date=end_date,
                record_count=0,
                files_read=[],
            )

        # Read and combine files
        dfs = []
        for file_path in files_to_read:
            df = pd.read_parquet(file_path)
            dfs.append(df)

        combined_df = pd.concat(dfs, ignore_index=True)

        # Filter by timestamp
        combined_df = combined_df[
            (combined_df["ts_event"] >= start_ns) &
            (combined_df["ts_event"] <= end_ns)
        ]
        combined_df = combined_df.sort_values("ts_event")

        data = converter(combined_df)

        return CatalogQueryResult(
            data=data,
            instrument_id=instrument_id,
            start_date=start_date,
            end_date=end_date,
            record_count=len(data),
            files_read=files_to_read,
        )

    def validate_trade_ticks(
        self,
        instrument_id: str,
        start_date: str,
        end_date: str,
        max_gap_seconds: float = 3600.0,
    ) -> ValidationResult:
        """
        Validate trade tick data quality.

        Args:
            instrument_id: Instrument ID to validate.
            start_date: Start date.
            end_date: End date.
            max_gap_seconds: Maximum allowed gap in seconds.

        Returns:
            ValidationResult with validation details.
        """
        result = self.read_trade_ticks(instrument_id, start_date, end_date)
        ticks = result.data

        if not ticks:
            return ValidationResult(
                is_valid=False,
                total_records=0,
                issues=["No data found for the specified range"],
                gaps=[],
            )

        issues: list[str] = []
        gaps: list[DataGap] = []
        max_gap_ns = int(max_gap_seconds * 1_000_000_000)

        # Check timestamp ordering
        for i in range(1, len(ticks)):
            if ticks[i].ts_event < ticks[i - 1].ts_event:
                issues.append(f"Timestamp out of order at index {i}")

        # Check for gaps
        for i in range(1, len(ticks)):
            gap_ns = ticks[i].ts_event - ticks[i - 1].ts_event
            if gap_ns > max_gap_ns:
                gaps.append(DataGap(
                    start_ts=ticks[i - 1].ts_event,
                    end_ts=ticks[i].ts_event,
                    missing_count=0,  # Unknown for trades
                    gap_type="time_gap",
                ))

        # Check for invalid prices/sizes (use explicit Decimal comparison)
        from decimal import Decimal
        zero = Decimal("0")
        for i, tick in enumerate(ticks):
            if tick.price <= zero:
                issues.append(f"Invalid price at index {i}: {tick.price}")
            if tick.size <= zero:
                issues.append(f"Invalid size at index {i}: {tick.size}")

        # Statistics
        prices = [float(t.price) for t in ticks]
        sizes = [float(t.size) for t in ticks]

        statistics = {
            "min_price": min(prices),
            "max_price": max(prices),
            "avg_price": sum(prices) / len(prices),
            "total_volume": sum(sizes),
            "num_gaps": len(gaps),
            "first_timestamp": ticks[0].ts_event,
            "last_timestamp": ticks[-1].ts_event,
        }

        return ValidationResult(
            is_valid=len(issues) == 0,
            total_records=len(ticks),
            issues=issues,
            gaps=gaps,
            statistics=statistics,
        )

    def get_catalog_info(self) -> CatalogInfo:
        """
        Get information about catalog contents.

        Returns:
            CatalogInfo with catalog details.
        """
        data_types: list[str] = []
        instruments: dict[str, list[str]] = {}
        date_ranges: dict[str, dict[str, tuple[str, str]]] = {}
        total_size = 0

        for data_type_dir in self.catalog_path.iterdir():
            if not data_type_dir.is_dir():
                continue

            data_type = data_type_dir.name
            data_types.append(data_type)
            instruments[data_type] = []
            date_ranges[data_type] = {}

            for instrument_dir in data_type_dir.iterdir():
                if not instrument_dir.is_dir():
                    continue

                instrument_id = instrument_dir.name
                instruments[data_type].append(instrument_id)

                # Find date range
                min_date = None
                max_date = None

                for year_dir in instrument_dir.iterdir():
                    if not year_dir.is_dir():
                        continue
                    for month_dir in year_dir.iterdir():
                        if not month_dir.is_dir():
                            continue

                        date_str = f"{year_dir.name}-{month_dir.name}"
                        if min_date is None or date_str < min_date:
                            min_date = date_str
                        if max_date is None or date_str > max_date:
                            max_date = date_str

                        # Count size
                        for file in month_dir.glob("*.parquet"):
                            total_size += file.stat().st_size

                if min_date and max_date:
                    date_ranges[data_type][instrument_id] = (min_date, max_date)

        return CatalogInfo(
            path=self.catalog_path,
            data_types=sorted(data_types),
            instruments=instruments,
            date_ranges=date_ranges,
            total_size_bytes=total_size,
        )

    def list_instruments(self, data_type: str = "trade_tick") -> list[str]:
        """
        List available instruments for a data type.

        Args:
            data_type: Data type to query.

        Returns:
            List of instrument IDs.
        """
        data_type_dir = self.catalog_path / data_type
        if not data_type_dir.exists():
            return []

        return [
            d.name for d in data_type_dir.iterdir()
            if d.is_dir()
        ]

    def delete_data(
        self,
        data_type: str,
        instrument_id: str,
        year: int | None = None,
        month: int | None = None,
    ) -> int:
        """
        Delete data from catalog.

        Args:
            data_type: Data type to delete.
            instrument_id: Instrument ID.
            year: Optional year filter.
            month: Optional month filter.

        Returns:
            Number of files deleted.
        """
        safe_instrument = instrument_id.replace("/", "_").replace(":", "_")
        base_path = self.catalog_path / data_type / safe_instrument

        if not base_path.exists():
            return 0

        deleted = 0

        if year is None:
            # Delete all data for instrument
            import shutil
            shutil.rmtree(base_path)
            deleted = 1
        elif month is None:
            # Delete all data for year
            year_path = base_path / str(year)
            if year_path.exists():
                import shutil
                shutil.rmtree(year_path)
                deleted = 1
        else:
            # Delete specific month
            month_path = base_path / str(year) / f"{month:02d}"
            if month_path.exists():
                import shutil
                shutil.rmtree(month_path)
                deleted = 1

        return deleted
