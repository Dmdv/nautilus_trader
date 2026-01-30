"""
NautilusTrader Configuration Module.

This module provides configuration classes for multi-exchange crypto trading
with support for Binance, Bybit, OKX, and dYdX exchanges.

Example:
    >>> from impl.config import (
    ...     load_environment,
    ...     BinanceConfig,
    ...     TradingNodeConfiguration,
    ... )
    >>> env = load_environment()
    >>> binance = BinanceConfig.from_env(env, testnet=True)
"""

from .env import (
    Environment,
    EnvironmentValidationError,
    load_environment,
    validate_api_credentials,
)
from .exchanges import (
    AccountType,
    BinanceAccountType,
    BinanceConfig,
    BybitAccountType,
    BybitConfig,
    DYDXConfig,
    DYDXNetwork,
    ExchangeConfig,
    OKXAccountType,
    OKXConfig,
    create_exchange_configs,
)
from .logging import (
    ComponentLogLevel,
    LogLevel,
    LoggingConfig,
    LogRotationConfig,
)
from .node import (
    CacheConfig,
    DataEngineConfig,
    ExecEngineConfig,
    TimeoutConfig,
    TradingNodeConfiguration,
)
from .redis import (
    RedisConfig,
    RedisPersistenceConfig,
    RedisSecurityConfig,
)

__all__ = [
    # Environment
    "Environment",
    "EnvironmentValidationError",
    "load_environment",
    "validate_api_credentials",
    # Exchanges
    "AccountType",
    "BinanceAccountType",
    "BinanceConfig",
    "BybitAccountType",
    "BybitConfig",
    "DYDXConfig",
    "DYDXNetwork",
    "ExchangeConfig",
    "OKXAccountType",
    "OKXConfig",
    "create_exchange_configs",
    # Logging
    "ComponentLogLevel",
    "LogLevel",
    "LoggingConfig",
    "LogRotationConfig",
    # Node
    "CacheConfig",
    "DataEngineConfig",
    "ExecEngineConfig",
    "TimeoutConfig",
    "TradingNodeConfiguration",
    # Redis
    "RedisConfig",
    "RedisPersistenceConfig",
    "RedisSecurityConfig",
]

__version__ = "0.1.0"
