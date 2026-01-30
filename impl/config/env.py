"""
Environment variable loading and validation for NautilusTrader.

This module provides utilities for loading and validating environment
variables used for exchange API credentials and system configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


class EnvironmentValidationError(Exception):
    """Raised when environment validation fails."""

    def __init__(self, message: str, missing_vars: list[str] | None = None) -> None:
        """
        Initialize the validation error.

        Args:
            message: Error description.
            missing_vars: List of missing environment variable names.
        """
        super().__init__(message)
        self.missing_vars = missing_vars or []


@dataclass(frozen=True)
class ExchangeCredentials:
    """
    Credentials for a single exchange.

    Attributes:
        api_key: The API key for authentication.
        api_secret: The API secret for signing requests.
        passphrase: Optional passphrase (required for OKX).
        mnemonic: Optional mnemonic phrase (for dYdX wallet).
        wallet_address: Optional wallet address (for dYdX).
    """

    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""
    mnemonic: str = ""
    wallet_address: str = ""

    def is_valid(self) -> bool:
        """Check if credentials have required fields populated."""
        return bool(self.api_key and self.api_secret)

    def is_dydx_valid(self) -> bool:
        """Check if dYdX-specific credentials are valid."""
        return bool(self.wallet_address)


@dataclass
class Environment:
    """
    Container for all environment configuration.

    This class holds all environment variables organized by exchange
    and provides methods for validation and serialization.

    Attributes:
        binance: Binance exchange credentials.
        bybit: Bybit exchange credentials.
        okx: OKX exchange credentials.
        dydx: dYdX exchange credentials.
        binance_testnet: Whether to use Binance testnet.
        bybit_testnet: Whether to use Bybit testnet.
        okx_testnet: Whether to use OKX testnet (demo).
        dydx_testnet: Whether to use dYdX testnet.
        redis_host: Redis server host.
        redis_port: Redis server port.
        redis_password: Redis authentication password.
        redis_db: Redis database number.
        log_level: Default logging level.
        log_file_path: Path for log files.
    """

    # Exchange credentials
    binance: ExchangeCredentials = field(default_factory=ExchangeCredentials)
    bybit: ExchangeCredentials = field(default_factory=ExchangeCredentials)
    okx: ExchangeCredentials = field(default_factory=ExchangeCredentials)
    dydx: ExchangeCredentials = field(default_factory=ExchangeCredentials)

    # Testnet flags
    binance_testnet: bool = True
    bybit_testnet: bool = True
    okx_testnet: bool = True
    dydx_testnet: bool = True

    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # Logging
    log_level: str = "INFO"
    log_file_path: str = "logs/"

    # Trader identification
    trader_id: str = "TRADER-001"
    instance_id: str = "INSTANCE-001"

    def get_enabled_exchanges(self) -> list[str]:
        """
        Get list of exchanges with valid credentials.

        Returns:
            List of exchange names that have valid credentials configured.
        """
        exchanges = []
        if self.binance.is_valid():
            exchanges.append("binance")
        if self.bybit.is_valid():
            exchanges.append("bybit")
        if self.okx.is_valid() and self.okx.passphrase:
            exchanges.append("okx")
        if self.dydx.is_dydx_valid():
            exchanges.append("dydx")
        return exchanges

    def validate_exchange(self, exchange: str) -> list[str]:
        """
        Validate credentials for a specific exchange.

        Args:
            exchange: Exchange name (binance, bybit, okx, dydx).

        Returns:
            List of missing environment variable names.
        """
        missing = []
        exchange_upper = exchange.upper()

        if exchange == "binance":
            if not self.binance.api_key:
                missing.append(f"{exchange_upper}_API_KEY")
            if not self.binance.api_secret:
                missing.append(f"{exchange_upper}_API_SECRET")
        elif exchange == "bybit":
            if not self.bybit.api_key:
                missing.append(f"{exchange_upper}_API_KEY")
            if not self.bybit.api_secret:
                missing.append(f"{exchange_upper}_API_SECRET")
        elif exchange == "okx":
            if not self.okx.api_key:
                missing.append(f"{exchange_upper}_API_KEY")
            if not self.okx.api_secret:
                missing.append(f"{exchange_upper}_API_SECRET")
            if not self.okx.passphrase:
                missing.append(f"{exchange_upper}_PASSPHRASE")
        elif exchange == "dydx":
            if not self.dydx.wallet_address:
                missing.append(f"{exchange_upper}_WALLET_ADDRESS")
            if not self.dydx.mnemonic and not self.dydx_testnet:
                missing.append(f"{exchange_upper}_MNEMONIC")

        return missing


def _parse_bool(value: str | None, default: bool = True) -> bool:
    """
    Parse a boolean from environment variable string.

    Args:
        value: String value to parse.
        default: Default value if parsing fails.

    Returns:
        Parsed boolean value.
    """
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def _parse_int(value: str | None, default: int) -> int:
    """
    Parse an integer from environment variable string.

    Args:
        value: String value to parse.
        default: Default value if parsing fails.

    Returns:
        Parsed integer value.
    """
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def load_dotenv(path: Path | str | None = None) -> dict[str, str]:
    """
    Load environment variables from a .env file.

    Args:
        path: Path to .env file. Defaults to current directory.

    Returns:
        Dictionary of loaded environment variables.
    """
    if path is None:
        path = Path.cwd() / ".env"
    else:
        path = Path(path)

    loaded: dict[str, str] = {}

    if not path.exists():
        return loaded

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse key=value pairs
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value and value[0] in ('"', "'") and value[-1] == value[0]:
                    value = value[1:-1]

                loaded[key] = value
                # Also set in environment
                os.environ.setdefault(key, value)

    return loaded


def load_environment(
    dotenv_path: Path | str | None = None,
    validate: bool = False,
    required_exchanges: list[str] | None = None,
) -> Environment:
    """
    Load environment configuration from environment variables.

    This function reads all relevant environment variables and returns
    an Environment object with the parsed configuration.

    Args:
        dotenv_path: Optional path to .env file to load.
        validate: If True, validate that required credentials exist.
        required_exchanges: List of exchanges that must have valid credentials.

    Returns:
        Environment object with loaded configuration.

    Raises:
        EnvironmentValidationError: If validation fails and validate=True.

    Example:
        >>> env = load_environment(".env", validate=True, required_exchanges=["binance"])
        >>> print(env.binance.api_key)
    """
    # Load .env file if specified or exists
    if dotenv_path or Path(".env").exists():
        load_dotenv(dotenv_path)

    # Build environment object
    env = Environment(
        # Binance
        binance=ExchangeCredentials(
            api_key=os.environ.get("BINANCE_API_KEY", ""),
            api_secret=os.environ.get("BINANCE_API_SECRET", ""),
        ),
        binance_testnet=_parse_bool(os.environ.get("BINANCE_TESTNET"), True),
        # Bybit
        bybit=ExchangeCredentials(
            api_key=os.environ.get("BYBIT_API_KEY", ""),
            api_secret=os.environ.get("BYBIT_API_SECRET", ""),
        ),
        bybit_testnet=_parse_bool(os.environ.get("BYBIT_TESTNET"), True),
        # OKX
        okx=ExchangeCredentials(
            api_key=os.environ.get("OKX_API_KEY", ""),
            api_secret=os.environ.get("OKX_API_SECRET", ""),
            passphrase=os.environ.get("OKX_PASSPHRASE", ""),
        ),
        okx_testnet=_parse_bool(os.environ.get("OKX_TESTNET"), True),
        # dYdX
        dydx=ExchangeCredentials(
            mnemonic=os.environ.get("DYDX_MNEMONIC", ""),
            wallet_address=os.environ.get("DYDX_WALLET_ADDRESS", ""),
        ),
        dydx_testnet=_parse_bool(
            os.environ.get("DYDX_TESTNET"),
            os.environ.get("DYDX_NETWORK", "testnet").lower() == "testnet",
        ),
        # Redis
        redis_host=os.environ.get("REDIS_HOST", "localhost"),
        redis_port=_parse_int(os.environ.get("REDIS_PORT"), 6379),
        redis_password=os.environ.get("REDIS_PASSWORD", ""),
        redis_db=_parse_int(os.environ.get("REDIS_DB"), 0),
        # Logging
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        log_file_path=os.environ.get("LOG_FILE_PATH", "logs/"),
        # Trader
        trader_id=os.environ.get("TRADER_ID", "TRADER-001"),
        instance_id=os.environ.get("INSTANCE_ID", "INSTANCE-001"),
    )

    # Validate if requested
    if validate and required_exchanges:
        all_missing: list[str] = []
        for exchange in required_exchanges:
            missing = env.validate_exchange(exchange)
            all_missing.extend(missing)

        if all_missing:
            raise EnvironmentValidationError(
                f"Missing required environment variables: {', '.join(all_missing)}",
                missing_vars=all_missing,
            )

    return env


def validate_api_credentials(
    api_key: str,
    api_secret: str,
    exchange: str = "generic",
) -> tuple[bool, list[str]]:
    """
    Validate API credential format.

    This performs basic format validation without making API calls.

    Args:
        api_key: The API key to validate.
        api_secret: The API secret to validate.
        exchange: Exchange name for exchange-specific validation.

    Returns:
        Tuple of (is_valid, list of error messages).

    Example:
        >>> valid, errors = validate_api_credentials("abc123", "secret456", "binance")
        >>> if not valid:
        ...     print(errors)
    """
    errors: list[str] = []

    # Check for empty values
    if not api_key:
        errors.append("API key is empty")
    if not api_secret:
        errors.append("API secret is empty")

    if errors:
        return False, errors

    # Check for whitespace
    if api_key != api_key.strip():
        errors.append("API key contains leading/trailing whitespace")
    if api_secret != api_secret.strip():
        errors.append("API secret contains leading/trailing whitespace")

    # Exchange-specific validation
    if exchange == "binance":
        # Binance keys are typically 64 characters
        if len(api_key) < 20:
            errors.append("Binance API key appears too short")
        # Check for common placeholder text
        if "your_api" in api_key.lower() or "xxx" in api_key.lower():
            errors.append("API key appears to be a placeholder value")

    elif exchange == "bybit":
        # Bybit keys have specific format
        if len(api_key) < 10:
            errors.append("Bybit API key appears too short")

    elif exchange == "okx":
        # OKX keys are typically UUID-like
        if len(api_key) < 10:
            errors.append("OKX API key appears too short")

    elif exchange == "dydx":
        # dYdX uses wallet addresses
        if api_key and not api_key.startswith("0x") and not api_key.startswith("dydx"):
            errors.append("dYdX wallet address should start with '0x' or 'dydx'")

    return len(errors) == 0, errors


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """
    Mask a secret value for safe logging.

    Args:
        value: The secret value to mask.
        visible_chars: Number of characters to show at end.

    Returns:
        Masked string with asterisks.

    Example:
        >>> mask_secret("my_secret_key_12345")
        '***************2345'
    """
    if not value:
        return ""
    if len(value) <= visible_chars:
        return "*" * len(value)
    return "*" * (len(value) - visible_chars) + value[-visible_chars:]
