"""
Deployment Modes Module.

Provides deployment infrastructure for different trading modes:
- Dry-run: Order logging without submission
- Shadow: Paper trading with comparison to live
- Paper: Testnet execution
- Production: Live trading with risk controls

Example:
    >>> from impl.deployment import DeploymentMode, DryRunConfig
    >>> from impl.deployment import CircuitBreaker, CircuitBreakerConfig
    >>> from impl.deployment import validate_deployment_readiness

Modules:
    - modes: Deployment mode definitions and configurations
    - dry_run: Dry-run order interception and validation
    - shadow: Shadow trading with fill simulation
    - validators: Pre-deployment validation checks
    - circuit_breaker: Risk controls and emergency stops
"""

from .modes import (
    DeploymentMode,
    DeploymentState,
    DeploymentConfig,
    DryRunConfig,
    ShadowConfig,
    PaperConfig,
    ProductionConfig,
    get_deployment_config,
)

from .dry_run import (
    DryRunOrder,
    DryRunOrderTracker,
    DryRunMetrics,
    DryRunValidator,
)

from .shadow import (
    ShadowFill,
    ShadowPosition,
    ShadowOrderTracker,
    ShadowMetrics,
    ShadowValidator,
)

from .validators import (
    DeploymentCheck,
    DeploymentCheckResult,
    DeploymentValidationResult,
    DeploymentValidator,
    validate_deployment_readiness,
)

from .circuit_breaker import (
    CircuitBreakerState,
    CircuitBreakerTrigger,
    CircuitBreakerConfig,
    CircuitBreaker,
    CircuitBreakerEvent,
)

__all__ = [
    # Modes
    "DeploymentMode",
    "DeploymentState",
    "DeploymentConfig",
    "DryRunConfig",
    "ShadowConfig",
    "PaperConfig",
    "ProductionConfig",
    "get_deployment_config",
    # Dry-run
    "DryRunOrder",
    "DryRunOrderTracker",
    "DryRunMetrics",
    "DryRunValidator",
    # Shadow
    "ShadowFill",
    "ShadowPosition",
    "ShadowOrderTracker",
    "ShadowMetrics",
    "ShadowValidator",
    # Validators
    "DeploymentCheck",
    "DeploymentCheckResult",
    "DeploymentValidationResult",
    "DeploymentValidator",
    "validate_deployment_readiness",
    # Circuit breaker
    "CircuitBreakerState",
    "CircuitBreakerTrigger",
    "CircuitBreakerConfig",
    "CircuitBreaker",
    "CircuitBreakerEvent",
]

__version__ = "0.1.0"
