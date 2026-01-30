"""
Logging configuration for NautilusTrader.

This module provides configuration classes for logging levels,
component-specific logging, and log rotation settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class LogLevel(str, Enum):
    """
    Log level enumeration.

    Attributes:
        DEBUG: Detailed information for development/troubleshooting.
        INFO: General operational information (production default).
        WARNING: Important alerts that need attention.
        ERROR: Error conditions only.
        CRITICAL: Critical errors requiring immediate attention.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

    @classmethod
    def from_string(cls, level: str) -> "LogLevel":
        """
        Parse log level from string.

        Args:
            level: Log level string (case-insensitive).

        Returns:
            Corresponding LogLevel enum value.

        Raises:
            ValueError: If level string is not recognized.
        """
        level_upper = level.upper()
        try:
            return cls(level_upper)
        except ValueError:
            valid = ", ".join(l.value for l in cls)
            raise ValueError(f"Invalid log level '{level}'. Valid levels: {valid}")


@dataclass
class ComponentLogLevel:
    """
    Component-specific log level configuration.

    Attributes:
        component: Name of the component.
        level: Log level for this component.
    """

    component: str
    level: LogLevel

    @classmethod
    def data_engine(cls, level: LogLevel = LogLevel.INFO) -> "ComponentLogLevel":
        """Create DataEngine log level configuration."""
        return cls(component="DataEngine", level=level)

    @classmethod
    def exec_engine(cls, level: LogLevel = LogLevel.DEBUG) -> "ComponentLogLevel":
        """Create ExecEngine log level configuration."""
        return cls(component="ExecEngine", level=level)

    @classmethod
    def risk_engine(cls, level: LogLevel = LogLevel.WARNING) -> "ComponentLogLevel":
        """Create RiskEngine log level configuration."""
        return cls(component="RiskEngine", level=level)

    @classmethod
    def portfolio(cls, level: LogLevel = LogLevel.INFO) -> "ComponentLogLevel":
        """Create Portfolio log level configuration."""
        return cls(component="Portfolio", level=level)

    @classmethod
    def strategy(cls, level: LogLevel = LogLevel.DEBUG) -> "ComponentLogLevel":
        """Create Strategy log level configuration."""
        return cls(component="Strategy", level=level)


@dataclass
class LogRotationConfig:
    """
    Log rotation configuration.

    Based on logrotate configuration for production deployments.

    Attributes:
        enabled: Whether log rotation is enabled.
        rotation_interval: Rotation interval ('daily', 'weekly', 'monthly').
        retain_count: Number of rotated logs to keep.
        compress: Whether to compress rotated logs.
        delay_compress: Delay compression to next rotation.
        missing_ok: Don't error if log file is missing.
        not_if_empty: Don't rotate if log is empty.
        create_mode: File permissions for new log files.
        create_owner: Owner for new log files.
        create_group: Group for new log files.
    """

    enabled: bool = True
    rotation_interval: str = "daily"
    retain_count: int = 30
    compress: bool = True
    delay_compress: bool = True
    missing_ok: bool = True
    not_if_empty: bool = True
    create_mode: str = "0640"
    create_owner: str = "nautilus"
    create_group: str = "nautilus"

    def to_logrotate_config(self, log_path: str) -> str:
        """
        Generate logrotate configuration file content.

        Args:
            log_path: Path to log files (supports wildcards).

        Returns:
            Logrotate configuration file content.
        """
        lines = [
            f"{log_path} {{",
            f"    {self.rotation_interval}",
            f"    rotate {self.retain_count}",
        ]

        if self.compress:
            lines.append("    compress")
        if self.delay_compress:
            lines.append("    delaycompress")
        if self.missing_ok:
            lines.append("    missingok")
        if self.not_if_empty:
            lines.append("    notifempty")

        lines.append(f"    create {self.create_mode} {self.create_owner} {self.create_group}")
        lines.append("}")

        return "\n".join(lines)


@dataclass
class LoggingConfig:
    """
    Complete logging configuration.

    Provides configuration for console and file logging with
    component-level granularity.

    Attributes:
        level: Console logging level.
        file_level: File logging level.
        file_path: Directory for log files.
        file_name_pattern: Log file naming pattern.
        component_levels: Per-component log levels.
        rotation: Log rotation configuration.
        include_timestamp: Include timestamp in console output.
        include_component: Include component name in output.

    Example:
        >>> config = LoggingConfig.production()
        >>> print(config.level)
        INFO
    """

    level: LogLevel = LogLevel.INFO
    file_level: LogLevel = LogLevel.DEBUG
    file_path: str = "logs/"
    file_name_pattern: str = "nautilus_{timestamp}.log"
    component_levels: list[ComponentLogLevel] = field(default_factory=list)
    rotation: LogRotationConfig = field(default_factory=LogRotationConfig)
    include_timestamp: bool = True
    include_component: bool = True

    @classmethod
    def development(cls) -> "LoggingConfig":
        """
        Create development logging configuration.

        Development uses verbose DEBUG logging everywhere.

        Returns:
            LoggingConfig for development.
        """
        return cls(
            level=LogLevel.DEBUG,
            file_level=LogLevel.DEBUG,
            component_levels=[
                ComponentLogLevel.data_engine(LogLevel.DEBUG),
                ComponentLogLevel.exec_engine(LogLevel.DEBUG),
                ComponentLogLevel.risk_engine(LogLevel.DEBUG),
                ComponentLogLevel.portfolio(LogLevel.DEBUG),
                ComponentLogLevel.strategy(LogLevel.DEBUG),
            ],
            rotation=LogRotationConfig(enabled=False),
        )

    @classmethod
    def paper_trading(cls) -> "LoggingConfig":
        """
        Create paper trading logging configuration.

        Paper trading uses INFO console, DEBUG file for analysis.

        Returns:
            LoggingConfig for paper trading.
        """
        return cls(
            level=LogLevel.INFO,
            file_level=LogLevel.DEBUG,
            component_levels=[
                ComponentLogLevel.data_engine(LogLevel.INFO),
                ComponentLogLevel.exec_engine(LogLevel.DEBUG),
                ComponentLogLevel.risk_engine(LogLevel.WARNING),
                ComponentLogLevel.portfolio(LogLevel.INFO),
                ComponentLogLevel.strategy(LogLevel.DEBUG),
            ],
        )

    @classmethod
    def production(cls) -> "LoggingConfig":
        """
        Create production logging configuration.

        Production uses INFO everywhere for performance.

        Returns:
            LoggingConfig for production.
        """
        return cls(
            level=LogLevel.INFO,
            file_level=LogLevel.INFO,
            component_levels=[
                ComponentLogLevel.data_engine(LogLevel.INFO),
                ComponentLogLevel.exec_engine(LogLevel.INFO),
                ComponentLogLevel.risk_engine(LogLevel.WARNING),
                ComponentLogLevel.portfolio(LogLevel.INFO),
                ComponentLogLevel.strategy(LogLevel.INFO),
            ],
            rotation=LogRotationConfig(
                enabled=True,
                retain_count=30,
                compress=True,
            ),
        )

    def get_component_level(self, component: str) -> LogLevel:
        """
        Get log level for a specific component.

        Args:
            component: Component name.

        Returns:
            Log level for the component (or default level if not set).
        """
        for cl in self.component_levels:
            if cl.component == component:
                return cl.level
        return self.level

    def set_component_level(self, component: str, level: LogLevel) -> None:
        """
        Set log level for a specific component.

        Args:
            component: Component name.
            level: Log level to set.
        """
        for cl in self.component_levels:
            if cl.component == component:
                cl.level = level
                return
        self.component_levels.append(ComponentLogLevel(component, level))

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary for NautilusTrader configuration.

        Returns:
            Dictionary of logging configuration.
        """
        return {
            "log_level": self.level.value,
            "log_level_file": self.file_level.value,
            "log_file_path": self.file_path,
            "log_component_levels": {
                cl.component: cl.level.value for cl in self.component_levels
            },
        }

    def ensure_log_directory(self) -> Path:
        """
        Ensure the log directory exists.

        Returns:
            Path to the log directory.
        """
        log_dir = Path(self.file_path)
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir

    def get_logrotate_config_path(self) -> str:
        """
        Get the suggested path for logrotate configuration.

        Returns:
            Path string for logrotate config file.
        """
        return "/etc/logrotate.d/nautilus"

    def generate_logrotate_config(self) -> str:
        """
        Generate complete logrotate configuration.

        Returns:
            Logrotate configuration file content.
        """
        log_pattern = f"{self.file_path}/*.log"
        return self.rotation.to_logrotate_config(log_pattern)


def configure_logging(config: LoggingConfig) -> None:
    """
    Configure Python logging based on LoggingConfig.

    This sets up basic Python logging to complement NautilusTrader's
    internal logging system.

    Args:
        config: Logging configuration to apply.

    Example:
        >>> config = LoggingConfig.production()
        >>> configure_logging(config)
    """
    import logging
    import sys
    from datetime import datetime

    # Create log directory
    config.ensure_log_directory()

    # Map LogLevel to Python logging levels
    level_map = {
        LogLevel.DEBUG: logging.DEBUG,
        LogLevel.INFO: logging.INFO,
        LogLevel.WARNING: logging.WARNING,
        LogLevel.ERROR: logging.ERROR,
        LogLevel.CRITICAL: logging.CRITICAL,
    }

    # Create formatter
    format_parts = []
    if config.include_timestamp:
        format_parts.append("%(asctime)s")
    format_parts.append("%(levelname)s")
    if config.include_component:
        format_parts.append("%(name)s")
    format_parts.append("%(message)s")
    formatter = logging.Formatter(" - ".join(format_parts))

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level_map[config.level])
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(config.file_path) / config.file_name_pattern.format(timestamp=timestamp)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level_map[config.file_level])
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Configure component-specific loggers
    for cl in config.component_levels:
        component_logger = logging.getLogger(cl.component)
        component_logger.setLevel(level_map[cl.level])
