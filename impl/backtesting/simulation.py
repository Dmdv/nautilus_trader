"""
Exchange Simulation Models.

Provides realistic fill models and latency models for backtesting
that match actual exchange behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from nautilus_trader.backtest.models import FillModel, LatencyModel


class ExchangeType(Enum):
    """Supported exchange types for simulation."""

    BINANCE = "binance"
    BYBIT = "bybit"
    OKX = "okx"
    DYDX = "dydx"


@dataclass(frozen=True)
class ExchangeSimulationConfig:
    """
    Exchange-specific simulation parameters.

    Attributes:
        exchange: Exchange identifier.
        latency_base_ms: Base latency in milliseconds.
        latency_std_ms: Latency standard deviation in milliseconds.
        fill_prob_limit: Probability of limit order fill.
        fill_prob_stop: Probability of stop order fill.
        slippage_prob: Probability of slippage occurring.
        slippage_bps: Maximum slippage in basis points.
        gas_cost_usd: Gas cost per trade (for L2/DEX).
    """

    exchange: ExchangeType
    latency_base_ms: float
    latency_std_ms: float
    fill_prob_limit: float
    fill_prob_stop: float
    slippage_prob: float
    slippage_bps: float
    gas_cost_usd: float = 0.0


# Exchange-specific configurations based on empirical data
EXCHANGE_CONFIGS: dict[ExchangeType, ExchangeSimulationConfig] = {
    ExchangeType.BINANCE: ExchangeSimulationConfig(
        exchange=ExchangeType.BINANCE,
        latency_base_ms=50.0,
        latency_std_ms=20.0,
        fill_prob_limit=0.85,
        fill_prob_stop=0.95,
        slippage_prob=0.4,
        slippage_bps=1.5,
    ),
    ExchangeType.BYBIT: ExchangeSimulationConfig(
        exchange=ExchangeType.BYBIT,
        latency_base_ms=60.0,
        latency_std_ms=25.0,
        fill_prob_limit=0.80,
        fill_prob_stop=0.90,
        slippage_prob=0.5,
        slippage_bps=2.0,
    ),
    ExchangeType.OKX: ExchangeSimulationConfig(
        exchange=ExchangeType.OKX,
        latency_base_ms=55.0,
        latency_std_ms=22.0,
        fill_prob_limit=0.82,
        fill_prob_stop=0.92,
        slippage_prob=0.45,
        slippage_bps=1.8,
    ),
    ExchangeType.DYDX: ExchangeSimulationConfig(
        exchange=ExchangeType.DYDX,
        latency_base_ms=200.0,
        latency_std_ms=100.0,
        fill_prob_limit=0.70,
        fill_prob_stop=0.80,
        slippage_prob=0.6,
        slippage_bps=3.0,
        gas_cost_usd=0.5,
    ),
}


def get_exchange_config(exchange: str | ExchangeType) -> ExchangeSimulationConfig:
    """
    Get simulation configuration for an exchange.

    Args:
        exchange: Exchange name or type.

    Returns:
        Exchange simulation configuration.

    Raises:
        ValueError: If exchange not supported.
    """
    if isinstance(exchange, str):
        exchange_lower = exchange.lower()
        for ex_type in ExchangeType:
            if ex_type.value == exchange_lower:
                exchange = ex_type
                break
        else:
            raise ValueError(
                f"Unsupported exchange: {exchange}. "
                f"Supported: {[e.value for e in ExchangeType]}"
            )

    if exchange not in EXCHANGE_CONFIGS:
        raise ValueError(f"No configuration for exchange: {exchange}")

    return EXCHANGE_CONFIGS[exchange]


def create_fill_model(config: ExchangeSimulationConfig) -> FillModel:
    """
    Create a fill model from exchange configuration.

    Args:
        config: Exchange simulation configuration.

    Returns:
        NautilusTrader FillModel instance.
    """
    return FillModel(
        prob_fill_on_limit=config.fill_prob_limit,
        prob_fill_on_stop=config.fill_prob_stop,
        prob_slippage=config.slippage_prob,
        random_seed=42,  # Reproducible results
    )


def create_latency_model(config: ExchangeSimulationConfig) -> LatencyModel:
    """
    Create a latency model from exchange configuration.

    Args:
        config: Exchange simulation configuration.

    Returns:
        NautilusTrader LatencyModel instance.
    """
    # Convert ms to nanoseconds
    base_ns = int(config.latency_base_ms * 1_000_000)

    return LatencyModel(
        base_latency_nanos=base_ns,
        insert_latency_nanos=base_ns // 5,  # Typically faster than base
        update_latency_nanos=base_ns // 5,
        cancel_latency_nanos=base_ns // 5,
    )


def create_simulation_models(
    exchange: str | ExchangeType,
) -> tuple[FillModel, LatencyModel]:
    """
    Create both fill and latency models for an exchange.

    Args:
        exchange: Exchange name or type.

    Returns:
        Tuple of (FillModel, LatencyModel).
    """
    config = get_exchange_config(exchange)
    return create_fill_model(config), create_latency_model(config)


@dataclass
class VenueSimulationParams:
    """
    Complete venue simulation parameters.

    Contains all configuration needed to simulate a trading venue
    with realistic market behavior.
    """

    exchange: ExchangeType
    fill_model: FillModel
    latency_model: LatencyModel
    config: ExchangeSimulationConfig

    @classmethod
    def from_exchange(cls, exchange: str | ExchangeType) -> VenueSimulationParams:
        """
        Create venue simulation parameters from exchange name.

        Args:
            exchange: Exchange name or type.

        Returns:
            Complete venue simulation parameters.
        """
        config = get_exchange_config(exchange)
        fill_model = create_fill_model(config)
        latency_model = create_latency_model(config)

        ex_type = (
            exchange if isinstance(exchange, ExchangeType)
            else ExchangeType(exchange.lower())
        )

        return cls(
            exchange=ex_type,
            fill_model=fill_model,
            latency_model=latency_model,
            config=config,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "exchange": self.exchange.value,
            "latency_base_ms": self.config.latency_base_ms,
            "latency_std_ms": self.config.latency_std_ms,
            "fill_prob_limit": self.config.fill_prob_limit,
            "fill_prob_stop": self.config.fill_prob_stop,
            "slippage_prob": self.config.slippage_prob,
            "slippage_bps": self.config.slippage_bps,
            "gas_cost_usd": self.config.gas_cost_usd,
        }
