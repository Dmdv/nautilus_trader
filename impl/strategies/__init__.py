"""
NautilusTrader Strategy Templates.

This package provides production-ready trading strategy implementations
following NautilusTrader patterns for:
- Trend-following (EMA Cross)
- Market Making (Avellaneda-Stoikov)
- Statistical Arbitrage (Pairs Trading)

Each strategy includes proper order management, position tracking,
risk management, and P&L calculation.

Example:
    >>> from impl.strategies import EMACrossStrategy, EMACrossConfig
    >>> from impl.strategies import MarketMakingStrategy, MarketMakingConfig
    >>> from impl.strategies import PairsTradingStrategy, PairsTradingConfig

Modules:
    - base: Base strategy class with common functionality
    - ema_cross: EMA crossover trend-following strategy
    - market_making: Avellaneda-Stoikov market making with VPIN
    - pairs_trading: Statistical arbitrage with cointegration
    - signals: Signal generation utilities
    - risk: Position sizing and risk management
"""

# Base strategy exports
from .base import (
    BaseStrategyConfig,
    BaseStrategy,
)

# EMA Cross strategy exports
from .ema_cross import (
    EMACrossConfig,
    EMACrossStrategy,
)

# Market Making strategy exports
from .market_making import (
    MarketMakingConfig,
    MarketMakingStrategy,
)

# Pairs Trading strategy exports
from .pairs_trading import (
    PairsTradingConfig,
    PairsTradingStrategy,
)

# Signal utilities exports
from .signals import (
    Signal,
    SignalType,
    SignalStrength,
    EMASignalGenerator,
    VPINSignalGenerator,
    ZScoreSignalGenerator,
    CompositeSignalGenerator,
)

# Risk management exports
from .risk import (
    RiskConfig,
    RiskManager,
    PositionSizer,
    VolatilityEstimator,
    DrawdownMonitor,
    RiskMetrics,
)

__all__ = [
    # Base
    "BaseStrategyConfig",
    "BaseStrategy",
    # EMA Cross
    "EMACrossConfig",
    "EMACrossStrategy",
    # Market Making
    "MarketMakingConfig",
    "MarketMakingStrategy",
    # Pairs Trading
    "PairsTradingConfig",
    "PairsTradingStrategy",
    # Signals
    "Signal",
    "SignalType",
    "SignalStrength",
    "EMASignalGenerator",
    "VPINSignalGenerator",
    "ZScoreSignalGenerator",
    "CompositeSignalGenerator",
    # Risk
    "RiskConfig",
    "RiskManager",
    "PositionSizer",
    "VolatilityEstimator",
    "DrawdownMonitor",
    "RiskMetrics",
]

__version__ = "0.1.0"
