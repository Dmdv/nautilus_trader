"""
Deployment Modes and Configurations.

Defines the deployment mode types and their configurations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DeploymentMode(str, Enum):
    """
    Trading deployment modes.

    Follows the 5-stage deployment progression:
    BACKTEST -> DRY_RUN -> SHADOW -> PAPER -> PRODUCTION
    """

    BACKTEST = "backtest"
    DRY_RUN = "dry_run"
    SHADOW = "shadow"
    PAPER = "paper"
    PRODUCTION = "production"

    @property
    def is_live(self) -> bool:
        """Check if this mode involves live market data."""
        return self in (DeploymentMode.DRY_RUN, DeploymentMode.SHADOW,
                       DeploymentMode.PAPER, DeploymentMode.PRODUCTION)

    @property
    def is_execution_enabled(self) -> bool:
        """Check if this mode actually submits orders."""
        return self in (DeploymentMode.PAPER, DeploymentMode.PRODUCTION)

    @property
    def requires_validation(self) -> bool:
        """Check if mode promotion requires validation."""
        return self != DeploymentMode.BACKTEST

    def previous_mode(self) -> DeploymentMode | None:
        """Get the previous mode in progression."""
        order = [DeploymentMode.BACKTEST, DeploymentMode.DRY_RUN,
                 DeploymentMode.SHADOW, DeploymentMode.PAPER,
                 DeploymentMode.PRODUCTION]
        idx = order.index(self)
        return order[idx - 1] if idx > 0 else None

    def next_mode(self) -> DeploymentMode | None:
        """Get the next mode in progression."""
        order = [DeploymentMode.BACKTEST, DeploymentMode.DRY_RUN,
                 DeploymentMode.SHADOW, DeploymentMode.PAPER,
                 DeploymentMode.PRODUCTION]
        idx = order.index(self)
        return order[idx + 1] if idx < len(order) - 1 else None


class DeploymentState(str, Enum):
    """Deployment lifecycle states."""

    INITIALIZING = "initializing"
    VALIDATING = "validating"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class DeploymentConfig:
    """
    Base deployment configuration.

    Attributes:
        mode: Deployment mode.
        strategy_id: Strategy identifier.
        instruments: List of instruments to trade.
        enable_logging: Enable detailed logging.
        enable_metrics: Enable metrics collection.
        validation_required: Require validation before running.
        max_runtime_hours: Maximum runtime in hours (0 = unlimited).
        metadata: Additional configuration metadata.
    """

    mode: DeploymentMode
    strategy_id: str
    instruments: list[str] = field(default_factory=list)
    enable_logging: bool = True
    enable_metrics: bool = True
    validation_required: bool = True
    max_runtime_hours: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode.value,
            "strategy_id": self.strategy_id,
            "instruments": self.instruments,
            "enable_logging": self.enable_logging,
            "enable_metrics": self.enable_metrics,
            "validation_required": self.validation_required,
            "max_runtime_hours": self.max_runtime_hours,
            "metadata": self.metadata,
        }


@dataclass
class DryRunConfig(DeploymentConfig):
    """
    Dry-run mode configuration.

    Attributes:
        log_orders: Log all order intentions.
        track_fills: Track hypothetical fill prices.
        compare_to_live: Compare signals to live prices.
        min_signals: Minimum signals before promotion.
        max_slippage_tolerance: Max acceptable signal slippage.
    """

    log_orders: bool = True
    track_fills: bool = True
    compare_to_live: bool = True
    min_signals: int = 100
    max_slippage_tolerance: float = 0.005  # 0.5%

    def __post_init__(self) -> None:
        """Ensure mode is set correctly."""
        self.mode = DeploymentMode.DRY_RUN


@dataclass
class ShadowConfig(DeploymentConfig):
    """
    Shadow mode configuration.

    Attributes:
        track_hypothetical_pnl: Track what P&L would have been.
        compare_execution_quality: Compare hypothetical vs actual.
        min_runtime_hours: Minimum hours before promotion.
        max_tracking_error: Maximum acceptable tracking error.
        correlation_threshold: Minimum correlation with actual.
    """

    track_hypothetical_pnl: bool = True
    compare_execution_quality: bool = True
    min_runtime_hours: float = 24.0
    max_tracking_error: float = 0.01  # 1%
    correlation_threshold: float = 0.95

    def __post_init__(self) -> None:
        """Ensure mode is set correctly."""
        self.mode = DeploymentMode.SHADOW


@dataclass
class PaperConfig(DeploymentConfig):
    """
    Paper trading configuration.

    Attributes:
        use_testnet: Use exchange testnet.
        initial_balance: Initial paper balance.
        max_position_size: Maximum position size.
        min_profitable_days: Minimum profitable days before promotion.
        min_trades: Minimum trade count.
    """

    use_testnet: bool = True
    initial_balance: float = 100_000.0
    max_position_size: float = 10_000.0
    min_profitable_days: int = 5
    min_trades: int = 50

    def __post_init__(self) -> None:
        """Ensure mode is set correctly."""
        self.mode = DeploymentMode.PAPER


@dataclass
class ProductionConfig(DeploymentConfig):
    """
    Production mode configuration.

    Attributes:
        max_position_value: Maximum position value.
        max_daily_loss: Maximum daily loss allowed.
        max_drawdown: Maximum drawdown allowed.
        require_circuit_breaker: Require circuit breaker.
        require_reconciliation: Require position reconciliation.
        reconciliation_interval_mins: Reconciliation interval.
        emergency_contacts: Emergency contact list.
    """

    max_position_value: float = 100_000.0
    max_daily_loss: float = 5_000.0
    max_drawdown: float = 0.10  # 10%
    require_circuit_breaker: bool = True
    require_reconciliation: bool = True
    reconciliation_interval_mins: int = 15
    emergency_contacts: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Ensure mode is set correctly."""
        self.mode = DeploymentMode.PRODUCTION
        self.validation_required = True  # Always required for production


def get_deployment_config(
    mode: DeploymentMode | str,
    strategy_id: str,
    **kwargs: Any,
) -> DeploymentConfig:
    """
    Create deployment configuration for specified mode.

    Args:
        mode: Deployment mode.
        strategy_id: Strategy identifier.
        **kwargs: Additional configuration parameters.

    Returns:
        Appropriate DeploymentConfig subclass.
    """
    if isinstance(mode, str):
        mode = DeploymentMode(mode)

    config_classes: dict[DeploymentMode, type[DeploymentConfig]] = {
        DeploymentMode.BACKTEST: DeploymentConfig,
        DeploymentMode.DRY_RUN: DryRunConfig,
        DeploymentMode.SHADOW: ShadowConfig,
        DeploymentMode.PAPER: PaperConfig,
        DeploymentMode.PRODUCTION: ProductionConfig,
    }

    config_class = config_classes.get(mode, DeploymentConfig)
    return config_class(mode=mode, strategy_id=strategy_id, **kwargs)
