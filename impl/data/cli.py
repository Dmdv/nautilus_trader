"""
CLI interface for data operations.

Provides command-line entry points for data download, catalog management,
and validation with proper input validation via argparse.

Usage:
    python -m impl.data.cli download --symbol BTCUSDT --start 2024-01-01 --end 2024-12-31
    python -m impl.data.cli catalog-info
    python -m impl.data.cli validate
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def validate_symbol(value: str) -> str:
    """Validate symbol format (alphanumeric only)."""
    if not re.match(r"^[A-Z0-9]+$", value):
        raise argparse.ArgumentTypeError(
            f"Invalid symbol format: {value}. Must be uppercase alphanumeric (e.g., BTCUSDT)"
        )
    return value


def validate_date(value: str) -> str:
    """Validate date format (YYYY-MM-DD)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        raise argparse.ArgumentTypeError(
            f"Invalid date format: {value}. Must be YYYY-MM-DD"
        )
    # Also validate it's a real date
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid date: {value}. {e}")
    return value


def validate_exchange(value: str) -> str:
    """Validate exchange name."""
    valid_exchanges = [
        "binance",
        "binance-futures",
        "bybit",
        "bybit-spot",
        "okx",
        "okx-swap",
        "dydx",
    ]
    if value.lower() not in valid_exchanges:
        raise argparse.ArgumentTypeError(
            f"Invalid exchange: {value}. Valid options: {', '.join(valid_exchanges)}"
        )
    return value.lower()


def cmd_download(args: argparse.Namespace) -> int:
    """Execute download command."""
    from .download import download_historical_data, DownloadProgress

    def progress_callback(progress: DownloadProgress) -> None:
        """Print progress updates."""
        print(
            f"\rProgress: {progress.progress_percent:.1f}% "
            f"({progress.completed_jobs}/{progress.total_jobs}) "
            f"- {progress.bytes_downloaded / (1024*1024):.2f} MB",
            end="",
            flush=True,
        )

    logger.info(
        "Starting download: %s from %s (%s to %s)",
        args.symbol,
        args.exchange,
        args.start,
        args.end,
    )

    try:
        jobs = download_historical_data(
            exchanges=[args.exchange],
            symbols=[args.symbol],
            start_date=args.start,
            end_date=args.end,
            data_types=[args.data_type],
            catalog_path=args.catalog if args.import_catalog else None,
            max_workers=args.workers,
            progress_callback=progress_callback if not args.quiet else None,
        )
        print()  # Newline after progress

        # Summary
        completed = sum(1 for j in jobs if j.status.value == "completed")
        failed = sum(1 for j in jobs if j.status.value == "failed")

        if failed > 0:
            logger.error("Download completed with errors: %d failed", failed)
            return 1

        logger.info("Download completed successfully: %d jobs", completed)
        return 0

    except Exception as e:
        logger.exception("Download failed: %s", e)
        return 1


def cmd_catalog_info(args: argparse.Namespace) -> int:
    """Execute catalog-info command."""
    from .catalog import ParquetCatalogManager

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        logger.error("Catalog not found: %s", catalog_path)
        return 1

    try:
        mgr = ParquetCatalogManager(catalog_path)
        info = mgr.get_catalog_info()

        print(f"Catalog: {catalog_path}")
        print(f"Instruments: {info.instrument_count}")
        print(f"Date range: {info.start_date} to {info.end_date}")
        print(f"Total size: {info.total_size_mb:.1f} MB")
        print(f"Data types: {', '.join(info.data_types)}")

        if args.verbose:
            print("\nInstruments:")
            for inst in mgr.list_instruments()[:20]:
                print(f"  - {inst}")
            if len(mgr.list_instruments()) > 20:
                print(f"  ... and {len(mgr.list_instruments()) - 20} more")

        return 0

    except Exception as e:
        logger.exception("Failed to read catalog: %s", e)
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Execute validate command."""
    from .catalog import ParquetCatalogManager

    catalog_path = Path(args.catalog)
    if not catalog_path.exists():
        logger.error("Catalog not found: %s", catalog_path)
        return 1

    try:
        mgr = ParquetCatalogManager(catalog_path)
        gaps = mgr.find_gaps()

        if gaps:
            print(f"Found {len(gaps)} gaps:")
            for gap in gaps[:10]:
                print(f"  - {gap.instrument_id}: {gap.start} to {gap.end}")
            if len(gaps) > 10:
                print(f"  ... and {len(gaps) - 10} more")
            return 1
        else:
            print("✓ No gaps found")
            return 0

    except Exception as e:
        logger.exception("Validation failed: %s", e)
        return 1


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="impl.data.cli",
        description="NautilusTrader data management CLI",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Download command
    download_parser = subparsers.add_parser(
        "download",
        help="Download historical market data",
    )
    download_parser.add_argument(
        "--symbol", "-s",
        type=validate_symbol,
        required=True,
        help="Trading symbol (e.g., BTCUSDT)",
    )
    download_parser.add_argument(
        "--start",
        type=validate_date,
        required=True,
        help="Start date (YYYY-MM-DD)",
    )
    download_parser.add_argument(
        "--end",
        type=validate_date,
        required=True,
        help="End date (YYYY-MM-DD)",
    )
    download_parser.add_argument(
        "--exchange", "-e",
        type=validate_exchange,
        default="binance-futures",
        help="Exchange (default: binance-futures)",
    )
    download_parser.add_argument(
        "--data-type", "-t",
        choices=["trades", "quotes", "book_snapshot_5_100ms"],
        default="trades",
        help="Data type to download (default: trades)",
    )
    download_parser.add_argument(
        "--catalog", "-c",
        type=Path,
        default=Path("data/catalog"),
        help="Catalog path (default: data/catalog)",
    )
    download_parser.add_argument(
        "--no-import",
        dest="import_catalog",
        action="store_false",
        help="Skip importing to catalog",
    )
    download_parser.add_argument(
        "--workers", "-w",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    download_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output",
    )
    download_parser.set_defaults(func=cmd_download)

    # Catalog info command
    info_parser = subparsers.add_parser(
        "catalog-info",
        help="Show catalog statistics",
    )
    info_parser.add_argument(
        "--catalog", "-c",
        type=Path,
        default=Path("data/catalog"),
        help="Catalog path (default: data/catalog)",
    )
    info_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed information",
    )
    info_parser.set_defaults(func=cmd_catalog_info)

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate data integrity",
    )
    validate_parser.add_argument(
        "--catalog", "-c",
        type=Path,
        default=Path("data/catalog"),
        help="Catalog path (default: data/catalog)",
    )
    validate_parser.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
