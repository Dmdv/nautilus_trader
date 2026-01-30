"""
Batch download scripts for historical market data.

This module provides utilities for downloading historical data
from various sources (Tardis, exchanges) with support for:
- Parallel downloads
- Progress tracking
- Resume capability
- Automatic catalog integration

Example:
    >>> from impl.data.download import BatchDownloader, BatchDownloadConfig
    >>> config = BatchDownloadConfig(
    ...     exchanges=["binance-futures"],
    ...     symbols=["BTCUSDT", "ETHUSDT"],
    ...     start_date="2024-01-01",
    ...     end_date="2024-01-31",
    ...     data_types=["trades"],
    ... )
    >>> downloader = BatchDownloader(config)
    >>> results = downloader.run()
"""

from __future__ import annotations

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable

from .catalog import ParquetCatalogManager
from .symbols import ExchangeVenue, InstrumentIdBuilder
from .tardis import TardisDataType, TardisDownloader, TardisDownloaderConfig
from .wranglers import MockInstrument, TradeTickWrangler, WranglerConfig

logger = logging.getLogger(__name__)


class DownloadStatus(str, Enum):
    """Status of a download job."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DownloadJob:
    """
    A single download job.

    Attributes:
        exchange: Exchange to download from.
        symbol: Symbol to download.
        data_type: Type of data to download.
        start_date: Start date.
        end_date: End date.
        status: Current status.
        error_message: Error message if failed.
        files_downloaded: List of downloaded files.
        bytes_downloaded: Total bytes downloaded.
    """

    exchange: str
    symbol: str
    data_type: str
    start_date: str
    end_date: str
    status: DownloadStatus = DownloadStatus.PENDING
    error_message: str = ""
    files_downloaded: list[Path] = field(default_factory=list)
    bytes_downloaded: int = 0

    @property
    def job_id(self) -> str:
        """Get unique job identifier."""
        return f"{self.exchange}:{self.symbol}:{self.data_type}:{self.start_date}"


@dataclass
class DownloadProgress:
    """
    Progress of batch download.

    Attributes:
        total_jobs: Total number of jobs.
        completed_jobs: Number of completed jobs.
        failed_jobs: Number of failed jobs.
        current_job: Currently running job ID.
        bytes_downloaded: Total bytes downloaded.
        start_time: Download start time.
    """

    total_jobs: int
    completed_jobs: int = 0
    failed_jobs: int = 0
    current_job: str = ""
    bytes_downloaded: int = 0
    start_time: datetime = field(default_factory=datetime.now)

    @property
    def progress_percent(self) -> float:
        """Get progress as percentage."""
        if self.total_jobs == 0:
            return 100.0
        return (self.completed_jobs + self.failed_jobs) / self.total_jobs * 100

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        return (datetime.now() - self.start_time).total_seconds()

    @property
    def estimated_remaining_seconds(self) -> float:
        """Estimate remaining time."""
        if self.completed_jobs == 0:
            return 0.0
        rate = self.elapsed_seconds / self.completed_jobs
        remaining = self.total_jobs - self.completed_jobs - self.failed_jobs
        return rate * remaining


@dataclass
class BatchDownloadConfig:
    """
    Configuration for batch downloads.

    Attributes:
        exchanges: List of exchanges to download from.
        symbols: List of symbols to download.
        data_types: List of data types to download.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        download_dir: Directory for raw downloads.
        catalog_path: Path to Parquet catalog (None to skip import).
        max_workers: Maximum concurrent downloads.
        skip_existing: Skip if data already exists in catalog.
        retry_failed: Retry failed downloads.
        tardis_api_key: Tardis API key (uses env var if not set).
    """

    exchanges: list[str]
    symbols: list[str]
    data_types: list[str]
    start_date: str
    end_date: str
    download_dir: Path = field(default_factory=lambda: Path("data/raw/tardis"))
    catalog_path: Path | None = field(default_factory=lambda: Path("data/catalog"))
    max_workers: int = 4
    skip_existing: bool = True
    retry_failed: bool = True
    tardis_api_key: str = ""

    def __post_init__(self) -> None:
        """Load API key from environment if not set."""
        if not self.tardis_api_key:
            self.tardis_api_key = os.environ.get("TARDIS_API_KEY", "")
        if isinstance(self.download_dir, str):
            self.download_dir = Path(self.download_dir)
        if isinstance(self.catalog_path, str):
            self.catalog_path = Path(self.catalog_path)


class BatchDownloader:
    """
    Batch downloader for historical market data.

    Downloads data from multiple exchanges and symbols in parallel,
    with progress tracking and catalog integration.

    Example:
        >>> config = BatchDownloadConfig(
        ...     exchanges=["binance-futures"],
        ...     symbols=["BTCUSDT"],
        ...     data_types=["trades"],
        ...     start_date="2024-01-01",
        ...     end_date="2024-01-31",
        ... )
        >>> downloader = BatchDownloader(config)
        >>> results = downloader.run()
    """

    def __init__(
        self,
        config: BatchDownloadConfig,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
    ) -> None:
        """
        Initialize the batch downloader.

        Args:
            config: Download configuration.
            progress_callback: Optional callback for progress updates.
        """
        self.config = config
        self.progress_callback = progress_callback
        self.jobs: list[DownloadJob] = []
        self.progress = DownloadProgress(total_jobs=0)
        self._catalog: ParquetCatalogManager | None = None

        # Initialize Tardis downloader
        tardis_config = TardisDownloaderConfig(
            api_key=config.tardis_api_key,
            download_dir=config.download_dir,
            concurrency=config.max_workers,
        )
        self.tardis = TardisDownloader(tardis_config)

    def _create_jobs(self) -> list[DownloadJob]:
        """Create download jobs from configuration."""
        jobs: list[DownloadJob] = []

        for exchange in self.config.exchanges:
            for symbol in self.config.symbols:
                for data_type in self.config.data_types:
                    job = DownloadJob(
                        exchange=exchange,
                        symbol=symbol,
                        data_type=data_type,
                        start_date=self.config.start_date,
                        end_date=self.config.end_date,
                    )

                    # Check if should skip
                    if self.config.skip_existing and self._data_exists(job):
                        job.status = DownloadStatus.SKIPPED
                        logger.info("Skipping existing data: %s", job.job_id)
                    else:
                        job.status = DownloadStatus.PENDING

                    jobs.append(job)

        return jobs

    def _data_exists(self, job: DownloadJob) -> bool:
        """Check if data already exists in catalog."""
        if not self.config.catalog_path:
            return False

        if self._catalog is None:
            self._catalog = ParquetCatalogManager(self.config.catalog_path)

        # Build instrument ID
        try:
            venue = ExchangeVenue.from_tardis_name(job.exchange)
            builder = InstrumentIdBuilder()
            instrument_id = builder.build(job.symbol, venue)

            # Check if data exists
            data_type_map = {
                "trades": "trade_tick",
                "quotes": "quote_tick",
                "book_snapshot_5_100ms": "order_book_delta",
            }
            catalog_type = data_type_map.get(job.data_type, job.data_type)

            if self._catalog is None:
                return False
            instruments = self._catalog.list_instruments(catalog_type)
            return instrument_id in instruments or job.symbol in instruments
        except Exception:
            return False

    def _execute_job(self, job: DownloadJob) -> DownloadJob:
        """Execute a single download job."""
        job.status = DownloadStatus.IN_PROGRESS
        logger.info("Starting download: %s", job.job_id)

        try:
            result = self.tardis.download(
                exchange=job.exchange,
                data_types=[job.data_type],
                symbols=[job.symbol],
                from_date=job.start_date,
                to_date=job.end_date,
            )

            if result.success:
                job.status = DownloadStatus.COMPLETED
                job.files_downloaded = result.files_downloaded
                job.bytes_downloaded = result.bytes_downloaded
                logger.info(
                    "Completed download: %s (%d files, %.2f MB)",
                    job.job_id,
                    len(result.files_downloaded),
                    result.bytes_downloaded / (1024 * 1024),
                )
            else:
                job.status = DownloadStatus.FAILED
                job.error_message = "; ".join(result.errors)
                logger.error("Failed download: %s - %s", job.job_id, job.error_message)

        except Exception as e:
            job.status = DownloadStatus.FAILED
            job.error_message = str(e)
            logger.exception("Exception during download: %s", job.job_id)

        return job

    def _import_to_catalog(self, job: DownloadJob) -> None:
        """Import downloaded data to catalog."""
        if not self.config.catalog_path or not job.files_downloaded:
            return

        if self._catalog is None:
            self._catalog = ParquetCatalogManager(self.config.catalog_path)

        # Build instrument
        try:
            venue = ExchangeVenue.from_tardis_name(job.exchange)
            builder = InstrumentIdBuilder()
            instrument_id = builder.build(job.symbol, venue)
            instrument = MockInstrument.from_string(instrument_id)

            # Process and import based on data type
            if job.data_type == "trades":
                wrangler = TradeTickWrangler(
                    instrument,
                    WranglerConfig(timestamp_unit="us"),
                )
                for file_path in job.files_downloaded:
                    if file_path.suffix == ".gz" or ".csv" in file_path.name:
                        ticks = wrangler.process(file_path)
                        if ticks and self._catalog is not None:
                            self._catalog.write_trade_ticks(ticks)
                            logger.info(
                                "Imported %d trade ticks from %s",
                                len(ticks),
                                file_path.name,
                            )

        except Exception as e:
            logger.error("Failed to import %s to catalog: %s", job.job_id, e)

    def run(self, import_to_catalog: bool = True) -> list[DownloadJob]:
        """
        Run the batch download.

        Args:
            import_to_catalog: Whether to import data to catalog after download.

        Returns:
            List of completed DownloadJob objects.
        """
        # Create jobs
        self.jobs = self._create_jobs()
        pending_jobs = [j for j in self.jobs if j.status == DownloadStatus.PENDING]

        self.progress = DownloadProgress(
            total_jobs=len(self.jobs),
            completed_jobs=len([j for j in self.jobs if j.status == DownloadStatus.SKIPPED]),
        )

        if not pending_jobs:
            logger.info("No jobs to download (all skipped or already exist)")
            return self.jobs

        logger.info(
            "Starting batch download: %d jobs (%d skipped)",
            len(pending_jobs),
            len(self.jobs) - len(pending_jobs),
        )

        # Execute jobs in parallel
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_job = {
                executor.submit(self._execute_job, job): job
                for job in pending_jobs
            }

            for future in as_completed(future_to_job):
                job = future.result()

                if job.status == DownloadStatus.COMPLETED:
                    self.progress.completed_jobs += 1
                    self.progress.bytes_downloaded += job.bytes_downloaded

                    # Import to catalog if requested
                    if import_to_catalog:
                        self._import_to_catalog(job)
                else:
                    self.progress.failed_jobs += 1

                self.progress.current_job = job.job_id

                if self.progress_callback:
                    self.progress_callback(self.progress)

        # Summary
        completed = len([j for j in self.jobs if j.status == DownloadStatus.COMPLETED])
        failed = len([j for j in self.jobs if j.status == DownloadStatus.FAILED])
        skipped = len([j for j in self.jobs if j.status == DownloadStatus.SKIPPED])

        logger.info(
            "Batch download complete: %d completed, %d failed, %d skipped, %.2f MB total",
            completed,
            failed,
            skipped,
            self.progress.bytes_downloaded / (1024 * 1024),
        )

        return self.jobs

    def get_failed_jobs(self) -> list[DownloadJob]:
        """Get list of failed jobs."""
        return [j for j in self.jobs if j.status == DownloadStatus.FAILED]

    def retry_failed(self) -> list[DownloadJob]:
        """Retry failed jobs."""
        failed_jobs = self.get_failed_jobs()
        if not failed_jobs:
            return []

        logger.info("Retrying %d failed jobs", len(failed_jobs))

        for job in failed_jobs:
            job.status = DownloadStatus.PENDING
            job.error_message = ""

        # Re-run only failed jobs
        original_jobs = self.jobs
        self.jobs = failed_jobs

        results = self.run()

        self.jobs = original_jobs
        return results


def download_historical_data(
    exchanges: list[str],
    symbols: list[str],
    start_date: str,
    end_date: str,
    data_types: list[str] | None = None,
    catalog_path: str | Path | None = "data/catalog",
    max_workers: int = 4,
    progress_callback: Callable[[DownloadProgress], None] | None = None,
) -> list[DownloadJob]:
    """
    Convenience function for downloading historical data.

    Args:
        exchanges: List of Tardis exchange names.
        symbols: List of symbols to download.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        data_types: Data types to download. Defaults to ["trades"].
        catalog_path: Path to catalog for import. None to skip import.
        max_workers: Maximum concurrent downloads.
        progress_callback: Optional progress callback.

    Returns:
        List of DownloadJob objects.

    Example:
        >>> jobs = download_historical_data(
        ...     exchanges=["binance-futures"],
        ...     symbols=["BTCUSDT", "ETHUSDT"],
        ...     start_date="2024-01-01",
        ...     end_date="2024-01-31",
        ... )
    """
    if data_types is None:
        data_types = ["trades"]

    config = BatchDownloadConfig(
        exchanges=exchanges,
        symbols=symbols,
        data_types=data_types,
        start_date=start_date,
        end_date=end_date,
        catalog_path=Path(catalog_path) if catalog_path else None,
        max_workers=max_workers,
    )

    downloader = BatchDownloader(config, progress_callback)
    return downloader.run()


def create_date_chunks(
    start_date: str,
    end_date: str,
    chunk_days: int = 30,
) -> list[tuple[str, str]]:
    """
    Split date range into chunks for parallel downloading.

    Args:
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        chunk_days: Days per chunk.

    Returns:
        List of (start, end) date tuples.
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    chunks: list[tuple[str, str]] = []
    current = start

    while current < end:
        chunk_end = min(current + timedelta(days=chunk_days - 1), end)
        chunks.append((
            current.strftime("%Y-%m-%d"),
            chunk_end.strftime("%Y-%m-%d"),
        ))
        current = chunk_end + timedelta(days=1)

    return chunks


def download_with_resume(
    config: BatchDownloadConfig,
    state_file: Path | str | None = None,
) -> list[DownloadJob]:
    """
    Download with resume capability from a state file.

    Args:
        config: Download configuration.
        state_file: Path to state file. Defaults to download_dir/state.json.

    Returns:
        List of completed DownloadJob objects.
    """
    import json

    if state_file is None:
        state_file = config.download_dir / "download_state.json"
    else:
        state_file = Path(state_file)

    # Load existing state
    completed_jobs: set[str] = set()
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
            completed_jobs = set(state.get("completed", []))
        logger.info("Resuming download: %d jobs already completed", len(completed_jobs))

    # Run downloader
    downloader = BatchDownloader(config)
    downloader.jobs = downloader._create_jobs()

    # Mark already completed
    for job in downloader.jobs:
        if job.job_id in completed_jobs:
            job.status = DownloadStatus.SKIPPED

    results = downloader.run()

    # Save state atomically (write to temp then rename)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    completed = [j.job_id for j in results if j.status == DownloadStatus.COMPLETED]
    completed_jobs.update(completed)

    # Write to temp file first, then atomic rename
    temp_file = state_file.with_suffix(".tmp")
    with open(temp_file, "w") as f:
        json.dump({
            "completed": list(completed_jobs),
            "last_run": datetime.now().isoformat(),
        }, f, indent=2)

    # Atomic rename (POSIX-compliant)
    temp_file.rename(state_file)

    return results
