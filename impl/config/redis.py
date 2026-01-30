"""
Redis configuration for NautilusTrader state persistence.

This module provides configuration classes for Redis cache and persistence,
supporting both development and production deployments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .env import Environment


class AppendFsync(str, Enum):
    """
    Redis AOF fsync policy.

    Attributes:
        ALWAYS: Fsync on every write (safest but slowest).
        EVERYSEC: Fsync once per second (recommended).
        NO: Let OS handle fsync (fastest but least safe).
    """

    ALWAYS = "always"
    EVERYSEC = "everysec"
    NO = "no"


class MaxmemoryPolicy(str, Enum):
    """
    Redis memory eviction policies.

    Attributes:
        NOEVICTION: Don't evict, return error on memory limit.
        ALLKEYS_LRU: Evict least recently used keys.
        VOLATILE_LRU: Evict LRU keys with TTL set.
        ALLKEYS_LFU: Evict least frequently used keys.
        VOLATILE_LFU: Evict LFU keys with TTL set.
        ALLKEYS_RANDOM: Evict random keys.
        VOLATILE_RANDOM: Evict random keys with TTL set.
        VOLATILE_TTL: Evict keys with shortest TTL.
    """

    NOEVICTION = "noeviction"
    ALLKEYS_LRU = "allkeys-lru"
    VOLATILE_LRU = "volatile-lru"
    ALLKEYS_LFU = "allkeys-lfu"
    VOLATILE_LFU = "volatile-lfu"
    ALLKEYS_RANDOM = "allkeys-random"
    VOLATILE_RANDOM = "volatile-random"
    VOLATILE_TTL = "volatile-ttl"


@dataclass
class RedisPersistenceConfig:
    """
    Redis persistence configuration.

    Controls how Redis persists data to disk for recovery.

    Attributes:
        aof_enabled: Enable append-only file persistence.
        aof_fsync: AOF fsync policy.
        aof_rewrite_percentage: Trigger rewrite at this growth percentage.
        aof_rewrite_min_size: Minimum AOF size before rewrite.
        rdb_enabled: Enable RDB snapshots.
        rdb_save_seconds: RDB snapshot interval (seconds).
        rdb_save_changes: Minimum changes before RDB snapshot.
    """

    aof_enabled: bool = True
    aof_fsync: AppendFsync = AppendFsync.EVERYSEC
    aof_rewrite_percentage: int = 100
    aof_rewrite_min_size: str = "64mb"

    rdb_enabled: bool = False
    rdb_save_seconds: int = 900
    rdb_save_changes: int = 1

    def to_config_lines(self) -> list[str]:
        """
        Generate Redis configuration lines.

        Returns:
            List of Redis configuration directives.
        """
        lines = []

        # AOF configuration
        lines.append(f"appendonly {'yes' if self.aof_enabled else 'no'}")
        if self.aof_enabled:
            lines.append(f"appendfsync {self.aof_fsync.value}")
            lines.append(f"auto-aof-rewrite-percentage {self.aof_rewrite_percentage}")
            lines.append(f"auto-aof-rewrite-min-size {self.aof_rewrite_min_size}")

        # RDB configuration
        if self.rdb_enabled:
            lines.append(f"save {self.rdb_save_seconds} {self.rdb_save_changes}")
        else:
            lines.append('save ""')

        return lines


@dataclass
class RedisSecurityConfig:
    """
    Redis security configuration.

    Attributes:
        password: Redis authentication password.
        ssl: Enable SSL/TLS connection.
        ssl_cert_reqs: SSL certificate requirement level.
        bind_address: Address to bind to (use 127.0.0.1 for local only).
    """

    password: str = ""
    ssl: bool = False
    ssl_cert_reqs: str = "required"
    bind_address: str = "127.0.0.1"

    def to_config_lines(self) -> list[str]:
        """
        Generate Redis security configuration lines.

        Returns:
            List of Redis configuration directives.
        """
        lines = []

        if self.password:
            lines.append(f"requirepass {self.password}")

        lines.append(f"bind {self.bind_address}")

        return lines


@dataclass
class RedisConfig:
    """
    Complete Redis configuration.

    Provides configuration for Redis server connection and behavior,
    supporting both development and production deployments.

    Attributes:
        host: Redis server hostname.
        port: Redis server port.
        db: Redis database number (0-15).
        maxmemory: Maximum memory limit (e.g., "2gb").
        maxmemory_policy: Memory eviction policy.
        tcp_keepalive: TCP keepalive interval (seconds).
        timeout: Client idle timeout (0 = disabled).
        persistence: Persistence configuration.
        security: Security configuration.

    Example:
        >>> config = RedisConfig.production(
        ...     host="redis.internal",
        ...     password="secure_password",
        ... )
    """

    host: str = "localhost"
    port: int = 6379
    db: int = 0

    # Memory settings
    maxmemory: str = "2gb"
    maxmemory_policy: MaxmemoryPolicy = MaxmemoryPolicy.ALLKEYS_LRU

    # Connection settings
    tcp_keepalive: int = 300
    timeout: int = 0

    # Sub-configurations
    persistence: RedisPersistenceConfig = field(default_factory=RedisPersistenceConfig)
    security: RedisSecurityConfig = field(default_factory=RedisSecurityConfig)

    @classmethod
    def development(cls) -> "RedisConfig":
        """
        Create development Redis configuration.

        Development uses local Redis with minimal persistence.

        Returns:
            RedisConfig for development.
        """
        return cls(
            host="localhost",
            port=6379,
            db=0,
            maxmemory="256mb",
            persistence=RedisPersistenceConfig(aof_enabled=False, rdb_enabled=False),
            security=RedisSecurityConfig(password=""),
        )

    @classmethod
    def production(
        cls,
        host: str = "redis.internal",
        port: int = 6379,
        password: str = "",
        maxmemory: str = "2gb",
    ) -> "RedisConfig":
        """
        Create production Redis configuration.

        Production uses AOF persistence and authentication.

        Args:
            host: Redis server hostname.
            port: Redis server port.
            password: Redis authentication password.
            maxmemory: Maximum memory limit.

        Returns:
            RedisConfig for production.
        """
        return cls(
            host=host,
            port=port,
            db=0,
            maxmemory=maxmemory,
            maxmemory_policy=MaxmemoryPolicy.ALLKEYS_LRU,
            persistence=RedisPersistenceConfig(
                aof_enabled=True,
                aof_fsync=AppendFsync.EVERYSEC,
            ),
            security=RedisSecurityConfig(
                password=password,
                bind_address="0.0.0.0" if host != "localhost" else "127.0.0.1",
            ),
        )

    @classmethod
    def from_env(cls, env: "Environment") -> "RedisConfig":
        """
        Create configuration from environment.

        Args:
            env: Environment object with loaded configuration.

        Returns:
            RedisConfig from environment.
        """
        return cls(
            host=env.redis_host,
            port=env.redis_port,
            db=env.redis_db,
            security=RedisSecurityConfig(password=env.redis_password),
        )

    def get_connection_url(self) -> str:
        """
        Get Redis connection URL.

        Returns:
            Redis URL in format redis://[password@]host:port/db
        """
        if self.security.password:
            return f"redis://:{self.security.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"

    def to_connection_dict(self) -> dict[str, Any]:
        """
        Get connection parameters as dictionary.

        Returns:
            Dictionary of connection parameters for redis-py.
        """
        params: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "socket_keepalive": True,
            "socket_keepalive_options": {},
        }

        if self.security.password:
            params["password"] = self.security.password

        if self.security.ssl:
            params["ssl"] = True
            params["ssl_cert_reqs"] = self.security.ssl_cert_reqs

        return params

    def to_config_file(self) -> str:
        """
        Generate complete Redis configuration file content.

        Returns:
            Redis configuration file content.
        """
        lines = [
            "# Redis Configuration",
            "# Generated by NautilusTrader Config",
            "",
            "# Memory management",
            f"maxmemory {self.maxmemory}",
            f"maxmemory-policy {self.maxmemory_policy.value}",
            "",
            "# Performance",
            f"tcp-keepalive {self.tcp_keepalive}",
            f"timeout {self.timeout}",
            "",
            "# Persistence",
        ]
        lines.extend(self.persistence.to_config_lines())

        lines.append("")
        lines.append("# Security")
        lines.extend(self.security.to_config_lines())

        return "\n".join(lines)

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate Redis configuration.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors: list[str] = []

        if self.port < 1 or self.port > 65535:
            errors.append(f"Invalid port number: {self.port}")

        if self.db < 0 or self.db > 15:
            errors.append(f"Invalid database number: {self.db} (must be 0-15)")

        if self.tcp_keepalive < 0:
            errors.append(f"Invalid tcp_keepalive: {self.tcp_keepalive}")

        return len(errors) == 0, errors


def check_redis_connection(config: RedisConfig) -> tuple[bool, str]:
    """
    Check Redis server connectivity.

    Args:
        config: Redis configuration to test.

    Returns:
        Tuple of (is_connected, status message).

    Example:
        >>> config = RedisConfig.development()
        >>> connected, message = check_redis_connection(config)
        >>> print(message)
    """
    try:
        import redis

        client = redis.Redis(**config.to_connection_dict())
        response = client.ping()
        if response:
            info = client.info("memory")
            used_memory = info.get("used_memory_human", "unknown")
            return True, f"Connected to Redis at {config.host}:{config.port} (memory: {used_memory})"
        return False, "Redis ping failed"
    except ImportError:
        return False, "redis-py package not installed"
    except Exception as e:
        return False, f"Connection failed: {e}"
