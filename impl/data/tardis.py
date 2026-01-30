"""
Tardis Machine API integration for historical crypto market data.

Tardis (https://tardis.dev) provides historical crypto market data with
millisecond precision for backtesting and research.

Supported Data Types:
    - trades: Executed trades
    - book_snapshot_*: Order book snapshots at various depths/intervals
    - incremental_book_L2: Level 2 order book updates
    - quotes: Best bid/ask quotes
    - derivative_ticker: Funding rates, open interest

Supported Exchanges:
    - binance-futures: Binance USDT-M Perpetuals (2019+)
    - binance: Binance Spot (2017+)
    - bybit: Bybit (2020+)
    - okex-swap: OKX Swaps (2020+)
    - dydx: dYdX (2021+)

Example:
    >>> from impl.data.tardis import TardisDownloader, TardisDataType
    >>> downloader = TardisDownloader()
    >>> downloader.download(
    ...     exchange="binance-futures",
    ...     data_types=[TardisDataType.TRADES],
    ...     symbols=["BTCUSDT"],
    ...     from_date="2024-01-01",
    ...     to_date="2024-01-31",
    ... )
"""

from __future__ import annotations

import gzip
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TardisExchange(str, Enum):
    """
    Supported Tardis exchanges.

    Each exchange has specific data availability dates and supported data types.
    """

    BINANCE = "binance"
    BINANCE_FUTURES = "binance-futures"
    BINANCE_DELIVERY = "binance-delivery"
    BYBIT = "bybit"
    OKX_SWAP = "okex-swap"
    OKX_FUTURES = "okex-futures"
    DYDX = "dydx"

    @property
    def data_available_from(self) -> str:
        """Get the earliest date data is available for this exchange."""
        dates = {
            TardisExchange.BINANCE: "2017-01-01",
            TardisExchange.BINANCE_FUTURES: "2019-09-08",
            TardisExchange.BINANCE_DELIVERY: "2020-01-01",
            TardisExchange.BYBIT: "2020-03-01",
            TardisExchange.OKX_SWAP: "2020-01-01",
            TardisExchange.OKX_FUTURES: "2020-01-01",
            TardisExchange.DYDX: "2021-04-01",
        }
        return dates.get(self, "2020-01-01")


class TardisDataType(str, Enum):
    """
    Available Tardis data types.

    Attributes:
        TRADES: Executed trades with price, size, side.
        BOOK_SNAPSHOT_5_100MS: Top 5 order book levels, 100ms intervals.
        BOOK_SNAPSHOT_25_100MS: Top 25 order book levels, 100ms intervals.
        BOOK_SNAPSHOT_5_1S: Top 5 order book levels, 1 second intervals.
        BOOK_SNAPSHOT_25_1S: Top 25 order book levels, 1 second intervals.
        INCREMENTAL_BOOK_L2: Level 2 order book delta updates.
        QUOTES: Best bid/ask quotes.
        DERIVATIVE_TICKER: Funding rate, open interest, mark price.
        LIQUIDATIONS: Forced liquidation events.
    """

    TRADES = "trades"
    BOOK_SNAPSHOT_5_100MS = "book_snapshot_5_100ms"
    BOOK_SNAPSHOT_25_100MS = "book_snapshot_25_100ms"
    BOOK_SNAPSHOT_5_1S = "book_snapshot_5_1s"
    BOOK_SNAPSHOT_25_1S = "book_snapshot_25_1s"
    INCREMENTAL_BOOK_L2 = "incremental_book_L2"
    QUOTES = "quotes"
    DERIVATIVE_TICKER = "derivative_ticker"
    LIQUIDATIONS = "liquidations"


@dataclass
class TardisDownloadResult:
    """
    Result of a Tardis download operation.

    Attributes:
        success: Whether the download completed successfully.
        files_downloaded: List of downloaded file paths.
        bytes_downloaded: Total bytes downloaded.
        errors: List of error messages if any.
        duration_seconds: Time taken for download.
    """

    success: bool
    files_downloaded: list[Path]
    bytes_downloaded: int
    errors: list[str]
    duration_seconds: float


@dataclass
class TardisDownloaderConfig:
    """
    Configuration for TardisDownloader.

    Attributes:
        api_key: Tardis API key. Defaults to TARDIS_API_KEY env var.
        download_dir: Directory for downloaded files.
        concurrency: Number of concurrent downloads.
        retry_count: Number of retry attempts on failure.
        retry_delay_seconds: Delay between retries.
        verify_checksums: Verify file checksums after download.
        decompress: Decompress .gz files after download.
    """

    api_key: str = ""
    download_dir: Path = field(default_factory=lambda: Path("data/raw/tardis"))
    concurrency: int = 4
    retry_count: int = 3
    retry_delay_seconds: float = 1.0
    verify_checksums: bool = True
    decompress: bool = False

    def __post_init__(self) -> None:
        """Load API key from environment if not provided."""
        if not self.api_key:
            self.api_key = os.environ.get("TARDIS_API_KEY", "")
        if isinstance(self.download_dir, str):
            self.download_dir = Path(self.download_dir)


class TardisDownloader:
    """
    Downloader for Tardis historical market data.

    This class provides methods for downloading historical data from Tardis
    with support for multiple exchanges, data types, and date ranges.

    Example:
        >>> downloader = TardisDownloader()
        >>> result = downloader.download(
        ...     exchange="binance-futures",
        ...     data_types=["trades"],
        ...     symbols=["BTCUSDT", "ETHUSDT"],
        ...     from_date="2024-01-01",
        ...     to_date="2024-01-31",
        ... )
        >>> print(f"Downloaded {len(result.files_downloaded)} files")
    """

    def __init__(self, config: TardisDownloaderConfig | None = None) -> None:
        """
        Initialize the Tardis downloader.

        Args:
            config: Downloader configuration. Uses defaults if not provided.
        """
        self.config = config or TardisDownloaderConfig()
        self._tardis_client: Any | None = None

    @property
    def is_configured(self) -> bool:
        """Check if the downloader is properly configured with API key."""
        return bool(self.config.api_key)

    def _get_tardis_client(self) -> Any:
        """
        Get or create the Tardis client.

        Returns:
            Tardis datasets module.

        Raises:
            ImportError: If tardis-dev is not installed.
            ValueError: If API key is not configured.
        """
        if self._tardis_client is not None:
            return self._tardis_client

        if not self.config.api_key:
            raise ValueError(
                "Tardis API key not configured. Set TARDIS_API_KEY environment "
                "variable or provide api_key in TardisDownloaderConfig."
            )

        try:
            from tardis_dev import datasets
            self._tardis_client = datasets
            return datasets
        except ImportError:
            raise ImportError(
                "tardis-dev package is not installed. "
                "Install with: pip install tardis-dev"
            )

    def download(
        self,
        exchange: str | TardisExchange,
        data_types: list[str | TardisDataType],
        symbols: list[str],
        from_date: str,
        to_date: str,
        download_dir: Path | str | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> TardisDownloadResult:
        """
        Download data from Tardis.

        This method downloads historical data for the specified exchange,
        data types, symbols, and date range.

        Args:
            exchange: Tardis exchange name (e.g., "binance-futures").
            data_types: List of data types to download.
            symbols: List of symbols to download (e.g., ["BTCUSDT"]).
            from_date: Start date (YYYY-MM-DD format).
            to_date: End date (YYYY-MM-DD format).
            download_dir: Override download directory.
            progress_callback: Optional callback for progress updates.
                Signature: (filename: str, current: int, total: int) -> None

        Returns:
            TardisDownloadResult with download statistics.

        Example:
            >>> downloader = TardisDownloader()
            >>> result = downloader.download(
            ...     exchange=TardisExchange.BINANCE_FUTURES,
            ...     data_types=[TardisDataType.TRADES],
            ...     symbols=["BTCUSDT"],
            ...     from_date="2024-01-01",
            ...     to_date="2024-01-31",
            ... )
        """
        start_time = datetime.now()
        errors: list[str] = []
        downloaded_files: list[Path] = []
        bytes_downloaded = 0

        # Normalize inputs
        exchange_str = exchange.value if isinstance(exchange, TardisExchange) else exchange
        data_type_strs = [
            dt.value if isinstance(dt, TardisDataType) else dt
            for dt in data_types
        ]
        symbols_upper = [s.upper() for s in symbols]

        # Determine download directory
        target_dir = Path(download_dir) if download_dir else self.config.download_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            "Starting Tardis download: exchange=%s, types=%s, symbols=%s, "
            "from=%s, to=%s, dir=%s",
            exchange_str,
            data_type_strs,
            symbols_upper,
            from_date,
            to_date,
            target_dir,
        )

        try:
            datasets = self._get_tardis_client()

            # Call Tardis download
            datasets.download(
                exchange=exchange_str,
                data_types=data_type_strs,
                from_date=from_date,
                to_date=to_date,
                symbols=symbols_upper,
                api_key=self.config.api_key,
                download_dir=str(target_dir),
            )

            # Find downloaded files
            downloaded_files = list(target_dir.glob(f"{exchange_str}_*"))
            for file in downloaded_files:
                if file.is_file():
                    bytes_downloaded += file.stat().st_size

            logger.info(
                "Tardis download complete: %d files, %.2f MB",
                len(downloaded_files),
                bytes_downloaded / (1024 * 1024),
            )

        except ImportError as e:
            errors.append(str(e))
            logger.error("Failed to import tardis-dev: %s", e)
        except ValueError as e:
            errors.append(str(e))
            logger.error("Configuration error: %s", e)
        except Exception as e:
            errors.append(f"Download failed: {e}")
            logger.exception("Tardis download failed")

        duration = (datetime.now() - start_time).total_seconds()

        return TardisDownloadResult(
            success=len(errors) == 0,
            files_downloaded=downloaded_files,
            bytes_downloaded=bytes_downloaded,
            errors=errors,
            duration_seconds=duration,
        )

    def download_trades(
        self,
        exchange: str | TardisExchange,
        symbols: list[str],
        from_date: str,
        to_date: str,
        download_dir: Path | str | None = None,
    ) -> TardisDownloadResult:
        """
        Download trade data from Tardis.

        Convenience method for downloading only trade data.

        Args:
            exchange: Tardis exchange name.
            symbols: List of symbols.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            download_dir: Override download directory.

        Returns:
            TardisDownloadResult with download statistics.
        """
        return self.download(
            exchange=exchange,
            data_types=[TardisDataType.TRADES],
            symbols=symbols,
            from_date=from_date,
            to_date=to_date,
            download_dir=download_dir,
        )

    def download_order_book(
        self,
        exchange: str | TardisExchange,
        symbols: list[str],
        from_date: str,
        to_date: str,
        depth: int = 5,
        interval_ms: int = 100,
        download_dir: Path | str | None = None,
    ) -> TardisDownloadResult:
        """
        Download order book snapshot data from Tardis.

        Args:
            exchange: Tardis exchange name.
            symbols: List of symbols.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            depth: Order book depth (5 or 25).
            interval_ms: Snapshot interval (100 or 1000).
            download_dir: Override download directory.

        Returns:
            TardisDownloadResult with download statistics.
        """
        # Map to correct data type
        if depth == 5 and interval_ms == 100:
            data_type = TardisDataType.BOOK_SNAPSHOT_5_100MS
        elif depth == 25 and interval_ms == 100:
            data_type = TardisDataType.BOOK_SNAPSHOT_25_100MS
        elif depth == 5 and interval_ms == 1000:
            data_type = TardisDataType.BOOK_SNAPSHOT_5_1S
        elif depth == 25 and interval_ms == 1000:
            data_type = TardisDataType.BOOK_SNAPSHOT_25_1S
        else:
            raise ValueError(f"Unsupported depth/interval: {depth}/{interval_ms}")

        return self.download(
            exchange=exchange,
            data_types=[data_type],
            symbols=symbols,
            from_date=from_date,
            to_date=to_date,
            download_dir=download_dir,
        )

    def download_quotes(
        self,
        exchange: str | TardisExchange,
        symbols: list[str],
        from_date: str,
        to_date: str,
        download_dir: Path | str | None = None,
    ) -> TardisDownloadResult:
        """
        Download quote (BBO) data from Tardis.

        Args:
            exchange: Tardis exchange name.
            symbols: List of symbols.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            download_dir: Override download directory.

        Returns:
            TardisDownloadResult with download statistics.
        """
        return self.download(
            exchange=exchange,
            data_types=[TardisDataType.QUOTES],
            symbols=symbols,
            from_date=from_date,
            to_date=to_date,
            download_dir=download_dir,
        )

    def download_incremental_book(
        self,
        exchange: str | TardisExchange,
        symbols: list[str],
        from_date: str,
        to_date: str,
        download_dir: Path | str | None = None,
    ) -> TardisDownloadResult:
        """
        Download incremental order book L2 data from Tardis.

        This data type provides individual order book update events
        for reconstructing the full order book state.

        Args:
            exchange: Tardis exchange name.
            symbols: List of symbols.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            download_dir: Override download directory.

        Returns:
            TardisDownloadResult with download statistics.
        """
        return self.download(
            exchange=exchange,
            data_types=[TardisDataType.INCREMENTAL_BOOK_L2],
            symbols=symbols,
            from_date=from_date,
            to_date=to_date,
            download_dir=download_dir,
        )

    def download_derivative_ticker(
        self,
        exchange: str | TardisExchange,
        symbols: list[str],
        from_date: str,
        to_date: str,
        download_dir: Path | str | None = None,
    ) -> TardisDownloadResult:
        """
        Download derivative ticker data (funding, OI) from Tardis.

        This includes funding rates, open interest, mark price,
        and other derivative-specific data.

        Args:
            exchange: Tardis exchange name.
            symbols: List of symbols.
            from_date: Start date (YYYY-MM-DD).
            to_date: End date (YYYY-MM-DD).
            download_dir: Override download directory.

        Returns:
            TardisDownloadResult with download statistics.
        """
        return self.download(
            exchange=exchange,
            data_types=[TardisDataType.DERIVATIVE_TICKER],
            symbols=symbols,
            from_date=from_date,
            to_date=to_date,
            download_dir=download_dir,
        )

    def list_available_symbols(
        self,
        exchange: str | TardisExchange,
        date: str | None = None,
    ) -> list[str]:
        """
        List available symbols for an exchange on a given date.

        Note: This requires making an API call to Tardis.

        Args:
            exchange: Tardis exchange name.
            date: Date to check (YYYY-MM-DD). Defaults to today.

        Returns:
            List of available symbol names.
        """
        # This would require HTTP API access
        # For now, return common symbols
        common_symbols = {
            "binance-futures": [
                "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT",
                "ADAUSDT", "DOGEUSDT", "MATICUSDT", "DOTUSDT", "AVAXUSDT",
            ],
            "bybit": [
                "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT",
            ],
            "okex-swap": [
                "BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP",
            ],
            "dydx": [
                "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "MATIC-USD",
            ],
        }
        exchange_str = exchange.value if isinstance(exchange, TardisExchange) else exchange
        return common_symbols.get(exchange_str, [])

    def estimate_download_size(
        self,
        exchange: str | TardisExchange,
        data_types: list[str | TardisDataType],
        symbols: list[str],
        from_date: str,
        to_date: str,
    ) -> dict[str, int | float]:
        """
        Estimate download size for a given request.

        NOTE: These are rough approximations based on typical data sizes.
        Actual download sizes may vary significantly (0.5x to 2x) depending
        on market activity, symbol liquidity, and data type.

        Args:
            exchange: Tardis exchange name.
            data_types: List of data types.
            symbols: List of symbols.
            from_date: Start date.
            to_date: End date.

        Returns:
            Dictionary with 'min_bytes', 'max_bytes', 'estimated_bytes'.
        """
        # Parse dates
        start = datetime.strptime(from_date, "%Y-%m-%d")
        end = datetime.strptime(to_date, "%Y-%m-%d")
        days = (end - start).days + 1

        # Rough size estimates per symbol per day (compressed)
        size_estimates = {
            TardisDataType.TRADES.value: 5_000_000,  # ~5MB/day
            TardisDataType.BOOK_SNAPSHOT_5_100MS.value: 50_000_000,  # ~50MB/day
            TardisDataType.BOOK_SNAPSHOT_25_100MS.value: 200_000_000,  # ~200MB/day
            TardisDataType.INCREMENTAL_BOOK_L2.value: 500_000_000,  # ~500MB/day
            TardisDataType.QUOTES.value: 10_000_000,  # ~10MB/day
            TardisDataType.DERIVATIVE_TICKER.value: 1_000_000,  # ~1MB/day
        }

        total_estimate = 0
        data_type_strs = [
            dt.value if isinstance(dt, TardisDataType) else dt
            for dt in data_types
        ]

        for dt in data_type_strs:
            per_day = size_estimates.get(dt, 10_000_000)
            total_estimate += per_day * len(symbols) * days

        return {
            "min_bytes": int(total_estimate * 0.5),
            "max_bytes": int(total_estimate * 2.0),
            "estimated_bytes": int(total_estimate),
            "estimated_mb": round(total_estimate / (1024 * 1024), 2),
        }


def decompress_tardis_file(
    file_path: Path,
    output_path: Path | None = None,
    delete_original: bool = False,
) -> Path:
    """
    Decompress a gzipped Tardis data file.

    Args:
        file_path: Path to the .gz file.
        output_path: Output path. Defaults to same path without .gz.
        delete_original: Delete the original .gz file after decompression.

    Returns:
        Path to the decompressed file.
    """
    if not file_path.suffix == ".gz":
        return file_path

    if output_path is None:
        output_path = file_path.with_suffix("")

    with gzip.open(file_path, "rb") as f_in:
        with open(output_path, "wb") as f_out:
            f_out.write(f_in.read())

    if delete_original:
        file_path.unlink()

    return output_path


def get_tardis_file_info(file_path: Path) -> dict[str, Any]:
    """
    Extract metadata from a Tardis filename.

    Tardis files follow the naming convention:
    {exchange}_{data_type}_{date}_{symbol}.csv.gz

    Args:
        file_path: Path to the Tardis data file.

    Returns:
        Dictionary with extracted metadata.
    """
    name = file_path.stem
    if name.endswith(".csv"):
        name = name[:-4]

    parts = name.split("_")
    if len(parts) < 4:
        return {"filename": file_path.name, "valid": False}

    return {
        "filename": file_path.name,
        "exchange": parts[0],
        "data_type": parts[1],
        "date": parts[2],
        "symbol": "_".join(parts[3:]),
        "valid": True,
        "size_bytes": file_path.stat().st_size if file_path.exists() else 0,
    }
