"""
TradingNode configuration for NautilusTrader.

This module provides configuration classes for the trading node,
including data engine, execution engine, cache, and timeout settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .env import Environment
    from .logging import LoggingConfig
    from .redis import RedisConfig


class CacheType(str, Enum):
    """
    Cache backend types.

    Attributes:
        MEMORY: In-memory cache (development only).
        REDIS: Redis-backed cache (recommended for production).
    """

    MEMORY = "memory"
    REDIS = "redis"


class EnvironmentType(str, Enum):
    """
    Deployment environment types.

    Attributes:
        DEVELOPMENT: Local development with debug settings.
        PAPER: Paper trading on testnet.
        PRODUCTION: Live trading on mainnet.
    """

    DEVELOPMENT = "development"
    PAPER = "paper"
    PRODUCTION = "production"


@dataclass
class TimeoutConfig:
    """
    Timeout configuration for trading node operations.

    All timeouts are in seconds.

    Attributes:
        connection: Connection establishment timeout.
        reconciliation: Position reconciliation timeout.
        portfolio: Portfolio calculation timeout.
        disconnection: Graceful disconnect timeout.
    """

    connection: float = 30.0
    reconciliation: float = 60.0
    portfolio: float = 10.0
    disconnection: float = 5.0

    @classmethod
    def for_exchange(cls, exchange: str) -> "TimeoutConfig":
        """
        Get exchange-specific timeout configuration.

        Args:
            exchange: Exchange name (binance, bybit, okx, dydx).

        Returns:
            TimeoutConfig with exchange-appropriate values.
        """
        # dYdX has longer timeouts due to L2 settlement
        if exchange.lower() == "dydx":
            return cls(
                connection=30.0,
                reconciliation=60.0,
                portfolio=10.0,
                disconnection=10.0,
            )
        # Standard exchanges have faster REST APIs
        return cls(
            connection=10.0,
            reconciliation=30.0,
            portfolio=10.0,
            disconnection=5.0,
        )


@dataclass
class CacheConfig:
    """
    Cache database configuration.

    Attributes:
        cache_type: Type of cache backend.
        host: Redis host (when using redis).
        port: Redis port (when using redis).
        db: Redis database number.
        password: Redis password (optional).
        ssl: Enable SSL for Redis connection.
    """

    cache_type: CacheType = CacheType.MEMORY
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    ssl: bool = False

    @classmethod
    def memory(cls) -> "CacheConfig":
        """Create in-memory cache configuration."""
        return cls(cache_type=CacheType.MEMORY)

    @classmethod
    def redis(
        cls,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str = "",
        ssl: bool = False,
    ) -> "CacheConfig":
        """
        Create Redis cache configuration.

        Args:
            host: Redis server host.
            port: Redis server port.
            db: Redis database number.
            password: Redis authentication password.
            ssl: Enable SSL/TLS connection.

        Returns:
            CacheConfig for Redis backend.
        """
        return cls(
            cache_type=CacheType.REDIS,
            host=host,
            port=port,
            db=db,
            password=password,
            ssl=ssl,
        )

    @classmethod
    def from_redis_config(cls, redis_config: "RedisConfig") -> "CacheConfig":
        """
        Create CacheConfig from RedisConfig.

        Args:
            redis_config: RedisConfig instance.

        Returns:
            CacheConfig configured for Redis.
        """
        return cls(
            cache_type=CacheType.REDIS,
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.db,
            password=redis_config.security.password if redis_config.security else "",
            ssl=redis_config.security.ssl if redis_config.security else False,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader CacheDatabaseConfig dict.

        Returns:
            Dictionary suitable for CacheDatabaseConfig initialization.
        """
        if self.cache_type == CacheType.MEMORY:
            return {"type": "memory"}

        config: dict[str, Any] = {
            "type": "redis",
            "host": self.host,
            "port": self.port,
            "db": self.db,
        }
        if self.password:
            config["password"] = self.password
        if self.ssl:
            config["ssl"] = self.ssl
        return config


@dataclass
class DataEngineConfig:
    """
    Live data engine configuration.

    Controls how market data is processed and validated.

    Attributes:
        time_bars_build_with_no_updates: Build time bars even without updates.
        time_bars_timestamp_on_close: Timestamp bars on close time.
        validate_data_sequence: Validate data sequence integrity.
    """

    time_bars_build_with_no_updates: bool = True
    time_bars_timestamp_on_close: bool = True
    validate_data_sequence: bool = True

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader LiveDataEngineConfig dict.

        Returns:
            Dictionary suitable for LiveDataEngineConfig initialization.
        """
        return {
            "time_bars_build_with_no_updates": self.time_bars_build_with_no_updates,
            "time_bars_timestamp_on_close": self.time_bars_timestamp_on_close,
            "validate_data_sequence": self.validate_data_sequence,
        }


@dataclass
class ExecEngineConfig:
    """
    Live execution engine configuration.

    Controls order execution and position reconciliation.

    Attributes:
        reconciliation: Enable position reconciliation.
        reconciliation_lookback_mins: Lookback period for reconciliation (minutes).
        filter_unclaimed_external_orders: Filter orders not created by this instance.
        filter_position_reports: Filter position reports.
    """

    reconciliation: bool = True
    reconciliation_lookback_mins: int = 1440  # 24 hours
    filter_unclaimed_external_orders: bool = True
    filter_position_reports: bool = False

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader LiveExecEngineConfig dict.

        Returns:
            Dictionary suitable for LiveExecEngineConfig initialization.
        """
        return {
            "reconciliation": self.reconciliation,
            "reconciliation_lookback_mins": self.reconciliation_lookback_mins,
            "filter_unclaimed_external_orders": self.filter_unclaimed_external_orders,
            "filter_position_reports": self.filter_position_reports,
        }


@dataclass
class TradingNodeConfiguration:
    """
    Complete trading node configuration.

    This is the main configuration class that combines all node settings
    into a single configuration object.

    Attributes:
        trader_id: Unique identifier for the trader.
        instance_id: Unique identifier for this instance.
        environment: Deployment environment type.
        log_level: Console logging level.
        log_level_file: File logging level.
        log_file_path: Directory for log files.
        log_component_levels: Per-component log levels.
        cache: Cache configuration.
        timeouts: Timeout configuration.
        data_engine: Data engine configuration.
        exec_engine: Execution engine configuration.

    Example:
        >>> config = TradingNodeConfiguration(
        ...     trader_id="TRADER-001",
        ...     environment=EnvironmentType.PAPER,
        ...     cache=CacheConfig.redis(host="localhost"),
        ... )
    """

    # Identification
    trader_id: str = "TRADER-001"
    instance_id: str = "INSTANCE-001"

    # Environment
    environment: EnvironmentType = EnvironmentType.DEVELOPMENT

    # Logging
    log_level: str = "INFO"
    log_level_file: str = "DEBUG"
    log_file_path: str = "logs/"
    log_component_levels: dict[str, str] = field(default_factory=dict)

    # Components
    cache: CacheConfig = field(default_factory=CacheConfig)
    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    data_engine: DataEngineConfig = field(default_factory=DataEngineConfig)
    exec_engine: ExecEngineConfig = field(default_factory=ExecEngineConfig)

    @classmethod
    def development(
        cls,
        trader_id: str = "DEV-001",
    ) -> "TradingNodeConfiguration":
        """
        Create development configuration.

        Development uses in-memory cache and verbose logging.

        Args:
            trader_id: Trader identifier.

        Returns:
            TradingNodeConfiguration for development.
        """
        return cls(
            trader_id=trader_id,
            instance_id=f"{trader_id}-DEV",
            environment=EnvironmentType.DEVELOPMENT,
            log_level="DEBUG",
            log_level_file="DEBUG",
            cache=CacheConfig.memory(),
            timeouts=TimeoutConfig(connection=10.0),
        )

    @classmethod
    def paper_trading(
        cls,
        trader_id: str = "PAPER-001",
        redis_host: str = "localhost",
        redis_port: int = 6379,
    ) -> "TradingNodeConfiguration":
        """
        Create paper trading (testnet) configuration.

        Paper trading uses Redis cache and moderate logging.

        Args:
            trader_id: Trader identifier.
            redis_host: Redis server host.
            redis_port: Redis server port.

        Returns:
            TradingNodeConfiguration for paper trading.
        """
        return cls(
            trader_id=trader_id,
            instance_id=f"{trader_id}-PAPER",
            environment=EnvironmentType.PAPER,
            log_level="INFO",
            log_level_file="DEBUG",
            cache=CacheConfig.redis(host=redis_host, port=redis_port),
            exec_engine=ExecEngineConfig(reconciliation=True),
        )

    @classmethod
    def production(
        cls,
        trader_id: str = "PROD-001",
        redis_host: str = "redis.internal",
        redis_port: int = 6379,
        redis_password: str = "",
    ) -> "TradingNodeConfiguration":
        """
        Create production configuration.

        Production uses Redis with authentication and reduced logging.

        Args:
            trader_id: Trader identifier.
            redis_host: Redis server host.
            redis_port: Redis server port.
            redis_password: Redis authentication password.

        Returns:
            TradingNodeConfiguration for production.
        """
        return cls(
            trader_id=trader_id,
            instance_id=f"{trader_id}-PROD",
            environment=EnvironmentType.PRODUCTION,
            log_level="INFO",
            log_level_file="INFO",
            cache=CacheConfig.redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
            ),
            exec_engine=ExecEngineConfig(
                reconciliation=True,
                reconciliation_lookback_mins=1440,
            ),
        )

    @classmethod
    def from_env(
        cls,
        env: "Environment",
        environment_type: EnvironmentType | None = None,
    ) -> "TradingNodeConfiguration":
        """
        Create configuration from environment.

        Args:
            env: Environment object with loaded configuration.
            environment_type: Override environment type.

        Returns:
            TradingNodeConfiguration from environment.
        """
        # Auto-detect environment type based on testnet flags
        if environment_type is None:
            if all([
                env.binance_testnet or not env.binance.is_valid(),
                env.bybit_testnet or not env.bybit.is_valid(),
                env.okx_testnet or not env.okx.is_valid(),
                env.dydx_testnet or not env.dydx.is_dydx_valid(),
            ]):
                environment_type = EnvironmentType.PAPER
            else:
                environment_type = EnvironmentType.PRODUCTION

        # Build cache config
        if env.redis_host and env.redis_host != "localhost":
            cache = CacheConfig.redis(
                host=env.redis_host,
                port=env.redis_port,
                db=env.redis_db,
                password=env.redis_password,
            )
        elif environment_type == EnvironmentType.DEVELOPMENT:
            cache = CacheConfig.memory()
        else:
            cache = CacheConfig.redis(
                host=env.redis_host,
                port=env.redis_port,
                db=env.redis_db,
                password=env.redis_password,
            )

        return cls(
            trader_id=env.trader_id,
            instance_id=env.instance_id,
            environment=environment_type,
            log_level=env.log_level,
            log_level_file=env.log_level if environment_type == EnvironmentType.PRODUCTION else "DEBUG",
            log_file_path=env.log_file_path,
            cache=cache,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader TradingNodeConfig dict.

        Returns:
            Dictionary suitable for TradingNodeConfig initialization.
        """
        config: dict[str, Any] = {
            "trader_id": self.trader_id,
            "instance_id": self.instance_id,
            "log_level": self.log_level,
            "log_level_file": self.log_level_file,
            "log_file_path": self.log_file_path,
            "timeout_connection": self.timeouts.connection,
            "timeout_reconciliation": self.timeouts.reconciliation,
            "timeout_portfolio": self.timeouts.portfolio,
            "timeout_disconnection": self.timeouts.disconnection,
            "data_engine": self.data_engine.to_dict(),
            "exec_engine": self.exec_engine.to_dict(),
        }

        # Add cache config (None for memory, dict for redis)
        if self.cache.cache_type == CacheType.REDIS:
            config["cache_database"] = self.cache.to_dict()
        else:
            config["cache_database"] = None

        # Add component log levels if specified
        if self.log_component_levels:
            config["log_component_levels"] = self.log_component_levels

        return config

    def with_logging(self, logging_config: "LoggingConfig") -> "TradingNodeConfiguration":
        """
        Apply logging configuration.

        Args:
            logging_config: Logging configuration to apply.

        Returns:
            New TradingNodeConfiguration with logging settings.
        """
        return TradingNodeConfiguration(
            trader_id=self.trader_id,
            instance_id=self.instance_id,
            environment=self.environment,
            log_level=logging_config.level.value,
            log_level_file=logging_config.file_level.value,
            log_file_path=logging_config.file_path,
            log_component_levels={
                c.component: c.level.value for c in logging_config.component_levels
            },
            cache=self.cache,
            timeouts=self.timeouts,
            data_engine=self.data_engine,
            exec_engine=self.exec_engine,
        )
