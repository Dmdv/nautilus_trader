"""
Quantitative Validation Framework.

This package provides comprehensive statistical validation tools for
trading strategies, including:
- Stationarity tests (ADF, Hurst exponent, half-life)
- Regime detection (HMM, rolling statistics)
- Complete validation pipeline with scoring

Example:
    >>> from impl.validation import validate_strategy, ValidationConfig
    >>> from impl.validation import run_stationarity_tests
    >>> from impl.validation import SimpleRegimeDetector

Modules:
    - stationarity: ADF test, Hurst exponent, half-life estimation
    - regime: Market regime detection and conditional analysis
    - validator: Complete validation pipeline
"""

# Stationarity exports
from .stationarity import (
    ADFResult,
    HurstResult,
    HalfLifeResult,
    StationarityTestSuite,
    adf_test,
    calculate_hurst_exponent,
    calculate_half_life,
    run_stationarity_tests,
)

# Regime exports
from .regime import (
    RegimeType,
    RegimeState,
    RegimeDetectionResult,
    RegimePerformance,
    SimpleRegimeDetector,
    HMMRegimeDetector,
    analyze_regime_performance,
)

# Validator exports
from .validator import (
    ValidationConfig,
    ValidationResult,
    StrategyValidator,
    validate_strategy,
)

__all__ = [
    # Stationarity
    "ADFResult",
    "HurstResult",
    "HalfLifeResult",
    "StationarityTestSuite",
    "adf_test",
    "calculate_hurst_exponent",
    "calculate_half_life",
    "run_stationarity_tests",
    # Regime
    "RegimeType",
    "RegimeState",
    "RegimeDetectionResult",
    "RegimePerformance",
    "SimpleRegimeDetector",
    "HMMRegimeDetector",
    "analyze_regime_performance",
    # Validator
    "ValidationConfig",
    "ValidationResult",
    "StrategyValidator",
    "validate_strategy",
]

__version__ = "0.1.0"
