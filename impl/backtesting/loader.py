"""
Backtest Data Loader.

Provides utilities for loading data from Parquet catalog
into BacktestEngine with proper time range handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from nautilus_trader.model.data import Bar, QuoteTick, TradeTick
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.persistence.catalog import ParquetDataCatalog


@dataclass
class DataLoadConfig:
    """
    Configuration for loading backtest data.

    Attributes:
        catalog_path: Path to Parquet catalog.
        instrument_ids: List of instrument IDs to load.
        start_time: Start time for data range.
        end_time: End time for data range.
        data_types: List of data types to load (trade_tick, quote_tick, bar).
        bar_types: List of bar types if loading bars (e.g., "1-MINUTE-LAST").
    """

    catalog_path: str | Path
    instrument_ids: list[str]
    start_time: datetime
    end_time: datetime
    data_types: list[str] | None = None
    bar_types: list[str] | None = None

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.data_types is None:
            self.data_types = ["bar"]

        if isinstance(self.catalog_path, str):
            self.catalog_path = Path(self.catalog_path)


class BacktestDataLoader:
    """
    Loader for backtest data from Parquet catalog.

    Provides methods to load various data types and validate
    data availability before running backtests.
    """

    def __init__(self, catalog_path: str | Path) -> None:
        """
        Initialize data loader.

        Args:
            catalog_path: Path to Parquet catalog root.
        """
        self.catalog_path = Path(catalog_path)

        if not self.catalog_path.exists():
            raise ValueError(f"Catalog path does not exist: {self.catalog_path}")

        self._catalog: ParquetDataCatalog | None = None

    @property
    def catalog(self) -> ParquetDataCatalog:
        """Get or create catalog instance."""
        if self._catalog is None:
            self._catalog = ParquetDataCatalog(str(self.catalog_path))
        return self._catalog

    def list_instruments(self) -> list[str]:
        """
        List all available instruments in catalog.

        Returns:
            List of instrument ID strings.
        """
        instruments = self.catalog.instruments()
        return [str(inst.id) for inst in instruments]

    def get_data_range(
        self,
        instrument_id: str,
        data_type: str = "bar",
    ) -> tuple[datetime | None, datetime | None]:
        """
        Get available data range for an instrument.

        Args:
            instrument_id: Instrument identifier.
            data_type: Type of data (bar, trade_tick, quote_tick).

        Returns:
            Tuple of (start_time, end_time) or (None, None) if no data.
        """
        inst_id = InstrumentId.from_str(instrument_id)

        try:
            if data_type == "bar":
                data = self.catalog.bars(instrument_ids=[inst_id])
            elif data_type == "trade_tick":
                data = self.catalog.trade_ticks(instrument_ids=[inst_id])
            elif data_type == "quote_tick":
                data = self.catalog.quote_ticks(instrument_ids=[inst_id])
            else:
                return None, None

            if not data:
                return None, None

            # Get time range from data
            times = [d.ts_event for d in data]
            if not times:
                return None, None

            min_time = pd.Timestamp(min(times), unit="ns").to_pydatetime()
            max_time = pd.Timestamp(max(times), unit="ns").to_pydatetime()

            return min_time, max_time

        except Exception:
            return None, None

    def validate_data_availability(
        self,
        config: DataLoadConfig,
    ) -> dict[str, Any]:
        """
        Validate that required data is available.

        Args:
            config: Data load configuration.

        Returns:
            Dictionary with validation results.
        """
        results: dict[str, Any] = {
            "valid": True,
            "instruments": {},
            "missing": [],
            "warnings": [],
        }

        for inst_id in config.instrument_ids:
            inst_result: dict[str, Any] = {"available": False, "data_types": {}}

            for data_type in config.data_types or ["bar"]:
                start, end = self.get_data_range(inst_id, data_type)

                if start is None or end is None:
                    inst_result["data_types"][data_type] = {
                        "available": False,
                        "reason": "No data found",
                    }
                    continue

                # Check if requested range is covered
                if start > config.start_time:
                    inst_result["data_types"][data_type] = {
                        "available": False,
                        "reason": f"Data starts at {start}, requested {config.start_time}",
                    }
                    results["warnings"].append(
                        f"{inst_id}: {data_type} data starts at {start}"
                    )
                elif end < config.end_time:
                    inst_result["data_types"][data_type] = {
                        "available": False,
                        "reason": f"Data ends at {end}, requested {config.end_time}",
                    }
                    results["warnings"].append(
                        f"{inst_id}: {data_type} data ends at {end}"
                    )
                else:
                    inst_result["data_types"][data_type] = {
                        "available": True,
                        "start": start,
                        "end": end,
                    }
                    inst_result["available"] = True

            results["instruments"][inst_id] = inst_result

            if not inst_result["available"]:
                results["missing"].append(inst_id)
                results["valid"] = False

        return results

    def load_bars(
        self,
        instrument_ids: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[Bar]:
        """
        Load bar data from catalog.

        Args:
            instrument_ids: List of instrument IDs.
            start_time: Optional start time filter.
            end_time: Optional end time filter.

        Returns:
            List of Bar objects.
        """
        inst_ids = [InstrumentId.from_str(i) for i in instrument_ids]

        start_ns = int(start_time.timestamp() * 1e9) if start_time else None
        end_ns = int(end_time.timestamp() * 1e9) if end_time else None

        return self.catalog.bars(
            instrument_ids=inst_ids,
            start=start_ns,
            end=end_ns,
        )

    def load_trade_ticks(
        self,
        instrument_ids: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[TradeTick]:
        """
        Load trade tick data from catalog.

        Args:
            instrument_ids: List of instrument IDs.
            start_time: Optional start time filter.
            end_time: Optional end time filter.

        Returns:
            List of TradeTick objects.
        """
        inst_ids = [InstrumentId.from_str(i) for i in instrument_ids]

        start_ns = int(start_time.timestamp() * 1e9) if start_time else None
        end_ns = int(end_time.timestamp() * 1e9) if end_time else None

        return self.catalog.trade_ticks(
            instrument_ids=inst_ids,
            start=start_ns,
            end=end_ns,
        )

    def load_quote_ticks(
        self,
        instrument_ids: list[str],
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[QuoteTick]:
        """
        Load quote tick data from catalog.

        Args:
            instrument_ids: List of instrument IDs.
            start_time: Optional start time filter.
            end_time: Optional end time filter.

        Returns:
            List of QuoteTick objects.
        """
        inst_ids = [InstrumentId.from_str(i) for i in instrument_ids]

        start_ns = int(start_time.timestamp() * 1e9) if start_time else None
        end_ns = int(end_time.timestamp() * 1e9) if end_time else None

        return self.catalog.quote_ticks(
            instrument_ids=inst_ids,
            start=start_ns,
            end=end_ns,
        )

    def get_catalog_stats(self) -> dict[str, Any]:
        """
        Get statistics about the catalog.

        Returns:
            Dictionary with catalog statistics.
        """
        instruments = self.list_instruments()

        stats: dict[str, Any] = {
            "path": str(self.catalog_path),
            "instrument_count": len(instruments),
            "instruments": {},
        }

        for inst_id in instruments[:10]:  # Limit to first 10 for performance
            start, end = self.get_data_range(inst_id, "bar")
            stats["instruments"][inst_id] = {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
            }

        if len(instruments) > 10:
            stats["note"] = f"Showing 10 of {len(instruments)} instruments"

        return stats
