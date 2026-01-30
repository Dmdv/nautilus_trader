"""
NautilusTrader Implementation Package.

This package contains production-ready implementations of trading system components
based on NautilusTrader, covering configuration, data ingestion, strategies,
backtesting, validation, and deployment.

Modules:
    - config: Exchange and system configuration
    - data: Data ingestion and catalog management
    - strategies: Trading strategy templates

Example:
    >>> from impl.config import load_environment, BinanceConfig
    >>> from impl.data import TardisDownloader, ParquetCatalogManager
    >>> from impl.strategies import EMACrossStrategy, MarketMakingStrategy
"""

# Configuration exports
from .config import (
    BinanceAccountType,
    BinanceConfig,
    BybitAccountType,
    BybitConfig,
    DYDXConfig,
    DYDXNetwork,
    Environment,
    EnvironmentValidationError,
    ExchangeConfig,
    OKXAccountType,
    OKXConfig,
    TradingNodeConfiguration,
    create_exchange_configs,
    load_environment,
)

# Data exports
from .data import (
    BarDataWrangler,
    BatchDownloadConfig,
    BatchDownloader,
    CatalogInfo,
    CatalogQueryResult,
    DataGap,
    DownloadJob,
    DownloadProgress,
    ExchangeVenue,
    InstrumentIdBuilder,
    InstrumentSpec,
    OrderBookDeltaWrangler,
    ParquetCatalogManager,
    QuoteTickWrangler,
    SymbolMapper,
    TardisDataType,
    TardisDownloader,
    TardisExchange,
    TradeTickWrangler,
    ValidationResult,
    WranglerConfig,
    download_historical_data,
    normalize_symbol,
    parse_instrument_id,
)

# Strategy exports
from .strategies import (
    BaseStrategy,
    BaseStrategyConfig,
    CompositeSignalGenerator,
    DrawdownMonitor,
    EMACrossConfig,
    EMACrossStrategy,
    EMASignalGenerator,
    MarketMakingConfig,
    MarketMakingStrategy,
    PairsTradingConfig,
    PairsTradingStrategy,
    PositionSizer,
    RiskConfig,
    RiskManager,
    RiskMetrics,
    Signal,
    SignalStrength,
    SignalType,
    VolatilityEstimator,
    VPINSignalGenerator,
    ZScoreSignalGenerator,
)

__all__ = [
    # Config
    "BinanceAccountType",
    "BinanceConfig",
    "BybitAccountType",
    "BybitConfig",
    "DYDXConfig",
    "DYDXNetwork",
    "Environment",
    "EnvironmentValidationError",
    "ExchangeConfig",
    "OKXAccountType",
    "OKXConfig",
    "TradingNodeConfiguration",
    "create_exchange_configs",
    "load_environment",
    # Data
    "BarDataWrangler",
    "BatchDownloadConfig",
    "BatchDownloader",
    "CatalogInfo",
    "CatalogQueryResult",
    "DataGap",
    "DownloadJob",
    "DownloadProgress",
    "ExchangeVenue",
    "InstrumentIdBuilder",
    "InstrumentSpec",
    "OrderBookDeltaWrangler",
    "ParquetCatalogManager",
    "QuoteTickWrangler",
    "SymbolMapper",
    "TardisDataType",
    "TardisDownloader",
    "TardisExchange",
    "TradeTickWrangler",
    "ValidationResult",
    "WranglerConfig",
    "download_historical_data",
    "normalize_symbol",
    "parse_instrument_id",
    # Strategies
    "BaseStrategy",
    "BaseStrategyConfig",
    "CompositeSignalGenerator",
    "DrawdownMonitor",
    "EMACrossConfig",
    "EMACrossStrategy",
    "EMASignalGenerator",
    "MarketMakingConfig",
    "MarketMakingStrategy",
    "PairsTradingConfig",
    "PairsTradingStrategy",
    "PositionSizer",
    "RiskConfig",
    "RiskManager",
    "RiskMetrics",
    "Signal",
    "SignalStrength",
    "SignalType",
    "VolatilityEstimator",
    "VPINSignalGenerator",
    "ZScoreSignalGenerator",
]

__version__ = "0.1.0"
