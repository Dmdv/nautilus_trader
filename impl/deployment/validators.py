"""
Deployment Validators.

Provides pre-deployment validation checks for each mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from .modes import DeploymentMode, DeploymentConfig


class DeploymentCheck(str, Enum):
    """Deployment validation check types."""

    # Common checks
    STRATEGY_EXISTS = "strategy_exists"
    INSTRUMENTS_VALID = "instruments_valid"
    CONFIG_VALID = "config_valid"
    DATA_AVAILABLE = "data_available"

    # Dry-run checks
    BACKTEST_PASSED = "backtest_passed"
    SIGNAL_QUALITY = "signal_quality"

    # Shadow checks
    DRY_RUN_PASSED = "dry_run_passed"
    SLIPPAGE_ACCEPTABLE = "slippage_acceptable"

    # Paper checks
    SHADOW_PASSED = "shadow_passed"
    TESTNET_CONNECTIVITY = "testnet_connectivity"
    ACCOUNT_BALANCE = "account_balance"

    # Production checks
    PAPER_PASSED = "paper_passed"
    MAINNET_CONNECTIVITY = "mainnet_connectivity"
    RISK_LIMITS_SET = "risk_limits_set"
    CIRCUIT_BREAKER_ENABLED = "circuit_breaker_enabled"
    RECONCILIATION_ENABLED = "reconciliation_enabled"
    EMERGENCY_CONTACTS = "emergency_contacts"


@dataclass
class DeploymentCheckResult:
    """
    Result of a deployment check.

    Attributes:
        check: Check type.
        passed: Whether check passed.
        message: Result message.
        severity: Severity level (error, warning, info).
        details: Additional details.
    """

    check: DeploymentCheck
    passed: bool
    message: str
    severity: str = "error"  # error, warning, info
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "check": self.check.value,
            "passed": self.passed,
            "message": self.message,
            "severity": self.severity,
            "details": self.details,
        }


@dataclass
class DeploymentValidationResult:
    """
    Complete deployment validation result.

    Attributes:
        mode: Deployment mode being validated.
        checks: List of check results.
        passed: Whether all required checks passed.
        can_promote: Whether promotion to this mode is allowed.
        warnings: Warning messages.
        timestamp: Validation timestamp.
    """

    mode: DeploymentMode
    checks: list[DeploymentCheckResult]
    passed: bool
    can_promote: bool
    warnings: list[str]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def failed_checks(self) -> list[DeploymentCheckResult]:
        """Get failed checks."""
        return [c for c in self.checks if not c.passed]

    @property
    def error_checks(self) -> list[DeploymentCheckResult]:
        """Get failed error-level checks."""
        return [c for c in self.checks if not c.passed and c.severity == "error"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "mode": self.mode.value,
            "checks": [c.to_dict() for c in self.checks],
            "passed": self.passed,
            "can_promote": self.can_promote,
            "warnings": self.warnings,
            "timestamp": self.timestamp.isoformat(),
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"Deployment Validation: {status}",
            f"Mode: {self.mode.value}",
            f"Can Promote: {'Yes' if self.can_promote else 'No'}",
            "=" * 50,
            "",
            "Checks:",
        ]

        for check in self.checks:
            icon = "✓" if check.passed else "✗"
            lines.append(f"  {icon} {check.check.value}: {check.message}")

        if self.warnings:
            lines.extend(["", "Warnings:"])
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        return "\n".join(lines)


class DeploymentValidator:
    """
    Validates deployment readiness for each mode.

    Runs appropriate checks based on deployment mode
    and previous validation results.
    """

    def __init__(self) -> None:
        """Initialize validator."""
        self._custom_checks: dict[DeploymentCheck, Callable[..., bool]] = {}

    def register_check(
        self,
        check: DeploymentCheck,
        check_func: Callable[..., bool],
    ) -> None:
        """
        Register a custom check function.

        Args:
            check: Check type.
            check_func: Function that returns True if check passes.
        """
        self._custom_checks[check] = check_func

    def validate(
        self,
        config: DeploymentConfig,
        previous_validation: DeploymentValidationResult | None = None,
    ) -> DeploymentValidationResult:
        """
        Validate deployment configuration.

        Args:
            config: Deployment configuration.
            previous_validation: Previous mode's validation result.

        Returns:
            DeploymentValidationResult with all checks.
        """
        checks: list[DeploymentCheckResult] = []
        warnings: list[str] = []

        # Common checks
        checks.extend(self._run_common_checks(config))

        # Mode-specific checks
        mode_checks = self._get_mode_checks(config.mode)
        for check in mode_checks:
            result = self._run_check(check, config, previous_validation)
            checks.append(result)

        # Check if previous mode validation is required
        if config.mode.requires_validation:
            prev_mode = config.mode.previous_mode()
            if prev_mode and previous_validation is None:
                warnings.append(
                    f"No validation result from {prev_mode.value} mode - "
                    "promotion may not be allowed"
                )
            elif prev_mode and previous_validation and not previous_validation.passed:
                warnings.append(
                    f"Previous {prev_mode.value} validation failed - "
                    "review issues before proceeding"
                )

        # Determine pass/fail
        error_checks = [c for c in checks if not c.passed and c.severity == "error"]
        passed = len(error_checks) == 0

        # Determine if promotion is allowed
        can_promote = passed
        if previous_validation is not None and not previous_validation.passed:
            can_promote = False

        return DeploymentValidationResult(
            mode=config.mode,
            checks=checks,
            passed=passed,
            can_promote=can_promote,
            warnings=warnings,
        )

    def _run_common_checks(
        self,
        config: DeploymentConfig,
    ) -> list[DeploymentCheckResult]:
        """Run checks common to all modes."""
        checks = []

        # Strategy exists check
        has_strategy = bool(config.strategy_id)
        checks.append(DeploymentCheckResult(
            check=DeploymentCheck.STRATEGY_EXISTS,
            passed=has_strategy,
            message="Strategy ID configured" if has_strategy else "No strategy ID",
        ))

        # Instruments valid check
        has_instruments = len(config.instruments) > 0
        checks.append(DeploymentCheckResult(
            check=DeploymentCheck.INSTRUMENTS_VALID,
            passed=has_instruments,
            message=f"{len(config.instruments)} instruments configured" if has_instruments
            else "No instruments configured",
            severity="warning" if not has_instruments else "info",
        ))

        # Config valid check
        checks.append(DeploymentCheckResult(
            check=DeploymentCheck.CONFIG_VALID,
            passed=True,
            message="Configuration is valid",
        ))

        return checks

    def _get_mode_checks(
        self,
        mode: DeploymentMode,
    ) -> list[DeploymentCheck]:
        """Get required checks for mode."""
        mode_check_map: dict[DeploymentMode, list[DeploymentCheck]] = {
            DeploymentMode.BACKTEST: [],
            DeploymentMode.DRY_RUN: [
                DeploymentCheck.BACKTEST_PASSED,
                DeploymentCheck.DATA_AVAILABLE,
            ],
            DeploymentMode.SHADOW: [
                DeploymentCheck.DRY_RUN_PASSED,
                DeploymentCheck.SLIPPAGE_ACCEPTABLE,
            ],
            DeploymentMode.PAPER: [
                DeploymentCheck.SHADOW_PASSED,
                DeploymentCheck.TESTNET_CONNECTIVITY,
                DeploymentCheck.ACCOUNT_BALANCE,
            ],
            DeploymentMode.PRODUCTION: [
                DeploymentCheck.PAPER_PASSED,
                DeploymentCheck.MAINNET_CONNECTIVITY,
                DeploymentCheck.RISK_LIMITS_SET,
                DeploymentCheck.CIRCUIT_BREAKER_ENABLED,
                DeploymentCheck.RECONCILIATION_ENABLED,
                DeploymentCheck.EMERGENCY_CONTACTS,
            ],
        }
        return mode_check_map.get(mode, [])

    def _run_check(
        self,
        check: DeploymentCheck,
        config: DeploymentConfig,
        previous_validation: DeploymentValidationResult | None,
    ) -> DeploymentCheckResult:
        """Run a specific check."""
        # Check if custom implementation exists
        if check in self._custom_checks:
            try:
                passed = self._custom_checks[check](config, previous_validation)
                return DeploymentCheckResult(
                    check=check,
                    passed=passed,
                    message=f"{check.value} {'passed' if passed else 'failed'}",
                )
            except Exception as e:
                return DeploymentCheckResult(
                    check=check,
                    passed=False,
                    message=f"Check error: {str(e)}",
                    details={"error": str(e)},
                )

        # Default check implementations
        return self._default_check(check, config, previous_validation)

    def _default_check(
        self,
        check: DeploymentCheck,
        config: DeploymentConfig,
        previous_validation: DeploymentValidationResult | None,
    ) -> DeploymentCheckResult:
        """Default check implementation."""
        # Previous mode checks
        if check in (
            DeploymentCheck.BACKTEST_PASSED,
            DeploymentCheck.DRY_RUN_PASSED,
            DeploymentCheck.SHADOW_PASSED,
            DeploymentCheck.PAPER_PASSED,
        ):
            if previous_validation is None:
                return DeploymentCheckResult(
                    check=check,
                    passed=False,
                    message="Previous mode validation not provided",
                )
            return DeploymentCheckResult(
                check=check,
                passed=previous_validation.passed,
                message="Previous mode validation " +
                        ("passed" if previous_validation.passed else "failed"),
            )

        # Connectivity checks - default to warning (requires implementation)
        if check in (
            DeploymentCheck.TESTNET_CONNECTIVITY,
            DeploymentCheck.MAINNET_CONNECTIVITY,
        ):
            return DeploymentCheckResult(
                check=check,
                passed=True,
                message="Connectivity check not implemented - skipping",
                severity="warning",
            )

        # Production-specific checks
        if check == DeploymentCheck.RISK_LIMITS_SET:
            # Check if production config has risk limits
            from .modes import ProductionConfig
            if isinstance(config, ProductionConfig):
                has_limits = config.max_position_value > 0 and config.max_daily_loss > 0
                return DeploymentCheckResult(
                    check=check,
                    passed=has_limits,
                    message="Risk limits configured" if has_limits else "Risk limits not set",
                )

        if check == DeploymentCheck.CIRCUIT_BREAKER_ENABLED:
            from .modes import ProductionConfig
            if isinstance(config, ProductionConfig):
                return DeploymentCheckResult(
                    check=check,
                    passed=config.require_circuit_breaker,
                    message="Circuit breaker " +
                            ("enabled" if config.require_circuit_breaker else "disabled"),
                )

        if check == DeploymentCheck.RECONCILIATION_ENABLED:
            from .modes import ProductionConfig
            if isinstance(config, ProductionConfig):
                return DeploymentCheckResult(
                    check=check,
                    passed=config.require_reconciliation,
                    message="Reconciliation " +
                            ("enabled" if config.require_reconciliation else "disabled"),
                )

        if check == DeploymentCheck.EMERGENCY_CONTACTS:
            from .modes import ProductionConfig
            if isinstance(config, ProductionConfig):
                has_contacts = len(config.emergency_contacts) > 0
                return DeploymentCheckResult(
                    check=check,
                    passed=has_contacts,
                    message=f"{len(config.emergency_contacts)} emergency contacts" if has_contacts
                    else "No emergency contacts",
                    severity="warning" if not has_contacts else "info",
                )

        # Default pass
        return DeploymentCheckResult(
            check=check,
            passed=True,
            message=f"{check.value} check not implemented",
            severity="warning",
        )


def validate_deployment_readiness(
    config: DeploymentConfig,
    previous_validation: DeploymentValidationResult | None = None,
) -> DeploymentValidationResult:
    """
    Convenience function to validate deployment readiness.

    Args:
        config: Deployment configuration.
        previous_validation: Previous mode's validation result.

    Returns:
        DeploymentValidationResult with all checks.
    """
    validator = DeploymentValidator()
    return validator.validate(config, previous_validation)
