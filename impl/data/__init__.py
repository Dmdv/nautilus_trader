"""
NautilusTrader Data Ingestion Module.

This module provides data ingestion capabilities for NautilusTrader,
supporting multiple data sources and exchanges including Binance, Bybit,
OKX, and dYdX.

Components:
    - tardis: Tardis Machine API integration for historical data
    - catalog: Parquet catalog management (load, query, validate)
    - wranglers: Data wranglers for bar aggregation, trade processing
    - symbols: Symbol/instrument ID utilities
    - download: Batch download scripts

Example:
    >>> from impl.data import (
    ...     TardisDownloader,
    ...     ParquetCatalogManager,
    ...     TradeTickWrangler,
    ...     BarDataWrangler,
    ...     InstrumentIdBuilder,
    ... )
    >>> # Download historical data from Tardis
    >>> downloader = TardisDownloader()
    >>> downloader.download_trades("binance-futures", ["BTCUSDT"], "2024-01-01", "2024-01-31")
    >>> # Load into catalog
    >>> catalog = ParquetCatalogManager("data/catalog")
    >>> catalog.write_trade_ticks(trade_ticks)
"""

from .catalog import (
    CatalogInfo,
    CatalogQueryResult,
    DataGap,
    ParquetCatalogManager,
    ValidationResult,
)
from .download import (
    BatchDownloadConfig,
    BatchDownloader,
    DownloadJob,
    DownloadProgress,
    download_historical_data,
)
from .symbols import (
    ExchangeVenue,
    InstrumentIdBuilder,
    InstrumentSpec,
    SymbolMapper,
    normalize_symbol,
    parse_instrument_id,
)
from .tardis import (
    TardisDataType,
    TardisDownloader,
    TardisExchange,
)
from .wranglers import (
    BarDataWrangler,
    OrderBookDeltaWrangler,
    QuoteTickWrangler,
    TradeTickWrangler,
    WranglerConfig,
)

__all__ = [
    # Tardis
    "TardisDataType",
    "TardisDownloader",
    "TardisExchange",
    # Catalog
    "CatalogInfo",
    "CatalogQueryResult",
    "DataGap",
    "ParquetCatalogManager",
    "ValidationResult",
    # Wranglers
    "BarDataWrangler",
    "OrderBookDeltaWrangler",
    "QuoteTickWrangler",
    "TradeTickWrangler",
    "WranglerConfig",
    # Symbols
    "ExchangeVenue",
    "InstrumentIdBuilder",
    "InstrumentSpec",
    "SymbolMapper",
    "normalize_symbol",
    "parse_instrument_id",
    # Download
    "BatchDownloadConfig",
    "BatchDownloader",
    "DownloadJob",
    "DownloadProgress",
    "download_historical_data",
]

__version__ = "0.1.0"
