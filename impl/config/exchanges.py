"""
Exchange client configurations for NautilusTrader.

This module provides configuration classes for Binance, Bybit, OKX, and dYdX
exchanges, supporting both testnet and mainnet environments.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .env import Environment


class BinanceAccountType(str, Enum):
    """
    Binance account types for different trading modes.

    Attributes:
        SPOT: Spot trading - buy/sell crypto directly.
        MARGIN: Cross/isolated margin - leveraged spot trading.
        USDT_FUTURE: USDT-margined perpetuals - most common for futures.
        COIN_FUTURE: Coin-margined perpetuals - inverse contracts.
    """

    SPOT = "SPOT"
    MARGIN = "MARGIN"
    USDT_FUTURE = "USDT_FUTURE"
    COIN_FUTURE = "COIN_FUTURE"


class BybitAccountType(str, Enum):
    """
    Bybit account types.

    Attributes:
        UNIFIED: Unified trading account - recommended for all products.
        CONTRACT: Legacy contract account - older perpetual contracts.
    """

    UNIFIED = "UNIFIED"
    CONTRACT = "CONTRACT"


class OKXAccountType(str, Enum):
    """
    OKX account types.

    Attributes:
        UNIFIED: Unified account with net position mode.
        PORTFOLIO_MARGIN: Portfolio margin with net position mode.
    """

    UNIFIED = "UNIFIED"
    PORTFOLIO_MARGIN = "PORTFOLIO_MARGIN"


class DYDXNetwork(str, Enum):
    """
    dYdX network endpoints.

    Attributes:
        TESTNET: Testnet for paper trading.
        MAINNET: Mainnet for live trading.
    """

    TESTNET = "testnet"
    MAINNET = "mainnet"


# Generic account type union
AccountType = BinanceAccountType | BybitAccountType | OKXAccountType


@dataclass
class RateLimitConfig:
    """
    Rate limiting configuration for exchange APIs.

    Attributes:
        requests_per_second: Maximum requests per second.
        requests_per_window: Maximum requests per time window.
        window_seconds: Time window in seconds.
        orders_per_second: Maximum orders per second.
    """

    requests_per_second: int = 10
    requests_per_window: int = 1200
    window_seconds: int = 60
    orders_per_second: int = 10


@dataclass
class ExchangeConfig(ABC):
    """
    Abstract base class for exchange configurations.

    This provides a common interface for all exchange configuration classes.

    Attributes:
        api_key: API key for authentication.
        api_secret: API secret for signing requests.
        testnet: Whether to use testnet endpoints.
        rate_limit: Rate limiting configuration.
    """

    api_key: str = ""
    api_secret: str = ""
    testnet: bool = True
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)

    @property
    @abstractmethod
    def exchange_name(self) -> str:
        """Get the exchange name."""
        ...

    @abstractmethod
    def to_data_client_config(self) -> dict[str, Any]:
        """Convert to NautilusTrader data client config dict."""
        ...

    @abstractmethod
    def to_exec_client_config(self) -> dict[str, Any]:
        """Convert to NautilusTrader execution client config dict."""
        ...

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the configuration.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors: list[str] = []
        if not self.api_key:
            errors.append(f"{self.exchange_name}: API key is required")
        if not self.api_secret:
            errors.append(f"{self.exchange_name}: API secret is required")
        return len(errors) == 0, errors


@dataclass
class BinanceConfig(ExchangeConfig):
    """
    Binance exchange configuration.

    Supports spot, margin, and futures trading with configurable
    rate limiting and position modes.

    Attributes:
        account_type: Type of Binance account.
        use_agg_trade_ticks: Use aggregated trades (recommended).
        use_position_ids: Track positions by ID.
        position_mode: Position mode ('one_way' or 'hedge').

    Example:
        >>> config = BinanceConfig(
        ...     api_key="your_key",
        ...     api_secret="your_secret",
        ...     account_type=BinanceAccountType.USDT_FUTURE,
        ...     testnet=True,
        ... )
    """

    account_type: BinanceAccountType = BinanceAccountType.USDT_FUTURE
    use_agg_trade_ticks: bool = True
    use_position_ids: bool = True
    position_mode: str = "one_way"

    def __post_init__(self) -> None:
        """Set Binance-specific rate limits."""
        if self.rate_limit.requests_per_second == 10:  # Default value
            self.rate_limit = RateLimitConfig(
                requests_per_second=10,
                requests_per_window=1200,
                window_seconds=60,
                orders_per_second=10,
            )

    @property
    def exchange_name(self) -> str:
        """Get the exchange name."""
        return "Binance"

    @classmethod
    def from_env(
        cls,
        env: "Environment",
        account_type: BinanceAccountType = BinanceAccountType.USDT_FUTURE,
        testnet: bool | None = None,
    ) -> "BinanceConfig":
        """
        Create configuration from environment.

        Args:
            env: Environment object with loaded credentials.
            account_type: Binance account type to use.
            testnet: Override testnet setting (uses env default if None).

        Returns:
            BinanceConfig instance.
        """
        return cls(
            api_key=env.binance.api_key,
            api_secret=env.binance.api_secret,
            testnet=testnet if testnet is not None else env.binance_testnet,
            account_type=account_type,
        )

    def to_data_client_config(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader BinanceDataClientConfig dict.

        Returns:
            Dictionary suitable for BinanceDataClientConfig initialization.
        """
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "account_type": self.account_type.value,
            "testnet": self.testnet,
            "rate_limit_per_second": self.rate_limit.requests_per_second,
            "use_agg_trade_ticks": self.use_agg_trade_ticks,
        }

    def to_exec_client_config(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader BinanceExecClientConfig dict.

        Returns:
            Dictionary suitable for BinanceExecClientConfig initialization.
        """
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "account_type": self.account_type.value,
            "testnet": self.testnet,
            "use_position_ids": self.use_position_ids,
        }


@dataclass
class BybitConfig(ExchangeConfig):
    """
    Bybit exchange configuration.

    Supports unified and contract account types with configurable
    rate limiting.

    Attributes:
        account_type: Type of Bybit account.

    Example:
        >>> config = BybitConfig(
        ...     api_key="your_key",
        ...     api_secret="your_secret",
        ...     account_type=BybitAccountType.UNIFIED,
        ...     testnet=True,
        ... )
    """

    account_type: BybitAccountType = BybitAccountType.UNIFIED

    def __post_init__(self) -> None:
        """Set Bybit-specific rate limits."""
        if self.rate_limit.requests_per_second == 10:  # Default value
            self.rate_limit = RateLimitConfig(
                requests_per_second=50,
                requests_per_window=120,
                window_seconds=5,
                orders_per_second=50,
            )

    @property
    def exchange_name(self) -> str:
        """Get the exchange name."""
        return "Bybit"

    @classmethod
    def from_env(
        cls,
        env: "Environment",
        account_type: BybitAccountType = BybitAccountType.UNIFIED,
        testnet: bool | None = None,
    ) -> "BybitConfig":
        """
        Create configuration from environment.

        Args:
            env: Environment object with loaded credentials.
            account_type: Bybit account type to use.
            testnet: Override testnet setting (uses env default if None).

        Returns:
            BybitConfig instance.
        """
        return cls(
            api_key=env.bybit.api_key,
            api_secret=env.bybit.api_secret,
            testnet=testnet if testnet is not None else env.bybit_testnet,
            account_type=account_type,
        )

    def to_data_client_config(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader BybitDataClientConfig dict.

        Returns:
            Dictionary suitable for BybitDataClientConfig initialization.
        """
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "account_type": self.account_type.value,
            "testnet": self.testnet,
        }

    def to_exec_client_config(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader BybitExecClientConfig dict.

        Returns:
            Dictionary suitable for BybitExecClientConfig initialization.
        """
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "account_type": self.account_type.value,
            "testnet": self.testnet,
        }


@dataclass
class OKXConfig(ExchangeConfig):
    """
    OKX exchange configuration.

    Requires passphrase in addition to API key/secret.

    Attributes:
        passphrase: OKX API passphrase (required).
        account_type: Type of OKX account.
        is_demo: Whether to use demo/testnet mode.

    Example:
        >>> config = OKXConfig(
        ...     api_key="your_key",
        ...     api_secret="your_secret",
        ...     passphrase="your_passphrase",
        ...     account_type=OKXAccountType.UNIFIED,
        ...     is_demo=True,
        ... )
    """

    passphrase: str = ""
    account_type: OKXAccountType = OKXAccountType.UNIFIED
    is_demo: bool = True

    def __post_init__(self) -> None:
        """Set OKX-specific rate limits and sync is_demo with testnet."""
        if self.rate_limit.requests_per_second == 10:  # Default value
            self.rate_limit = RateLimitConfig(
                requests_per_second=60,
                requests_per_window=300,
                window_seconds=2,
                orders_per_second=60,
            )
        # Sync is_demo with testnet flag
        self.is_demo = self.testnet

    @property
    def exchange_name(self) -> str:
        """Get the exchange name."""
        return "OKX"

    @classmethod
    def from_env(
        cls,
        env: "Environment",
        account_type: OKXAccountType = OKXAccountType.UNIFIED,
        testnet: bool | None = None,
    ) -> "OKXConfig":
        """
        Create configuration from environment.

        Args:
            env: Environment object with loaded credentials.
            account_type: OKX account type to use.
            testnet: Override testnet setting (uses env default if None).

        Returns:
            OKXConfig instance.
        """
        is_testnet = testnet if testnet is not None else env.okx_testnet
        return cls(
            api_key=env.okx.api_key,
            api_secret=env.okx.api_secret,
            passphrase=env.okx.passphrase,
            testnet=is_testnet,
            is_demo=is_testnet,
            account_type=account_type,
        )

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the configuration including passphrase.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        valid, errors = super().validate()
        if not self.passphrase:
            errors.append("OKX: Passphrase is required")
            valid = False
        return valid, errors

    def to_data_client_config(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader OKXDataClientConfig dict.

        Returns:
            Dictionary suitable for OKXDataClientConfig initialization.
        """
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "passphrase": self.passphrase,
            "account_type": self.account_type.value,
            "is_demo": self.is_demo,
        }

    def to_exec_client_config(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader OKXExecClientConfig dict.

        Returns:
            Dictionary suitable for OKXExecClientConfig initialization.
        """
        return {
            "api_key": self.api_key,
            "api_secret": self.api_secret,
            "passphrase": self.passphrase,
            "account_type": self.account_type.value,
            "is_demo": self.is_demo,
        }


@dataclass
class DYDXConfig:
    """
    dYdX exchange configuration.

    Uses wallet-based authentication instead of API keys.

    Attributes:
        wallet_address: dYdX wallet address.
        mnemonic: Wallet mnemonic phrase (testnet only!).
        is_testnet: Whether to use testnet.
        subaccount_number: dYdX subaccount number (default 0).
        network: Network configuration.

    Security Note:
        Never use mnemonic phrase for mainnet trading.
        Use hardware wallet integration instead.

    Example:
        >>> config = DYDXConfig(
        ...     wallet_address="dydx1abc...",
        ...     mnemonic="word1 word2 ...",  # Testnet only!
        ...     is_testnet=True,
        ... )
    """

    wallet_address: str = ""
    mnemonic: str = ""
    is_testnet: bool = True
    subaccount_number: int = 0
    network: DYDXNetwork = DYDXNetwork.TESTNET

    # Network endpoints
    _ENDPOINTS: dict[DYDXNetwork, dict[str, str]] = field(
        default_factory=lambda: {
            DYDXNetwork.TESTNET: {
                "indexer": "https://indexer.v4testnet.dydx.exchange",
                "validator": "https://test-dydx.kingnodes.com",
            },
            DYDXNetwork.MAINNET: {
                "indexer": "https://indexer.dydx.trade",
                "validator": "https://dydx-mainnet.kingnodes.com",
            },
        },
        repr=False,
    )

    def __post_init__(self) -> None:
        """Sync network with is_testnet flag."""
        self.network = DYDXNetwork.TESTNET if self.is_testnet else DYDXNetwork.MAINNET

    @property
    def exchange_name(self) -> str:
        """Get the exchange name."""
        return "dYdX"

    @property
    def indexer_url(self) -> str:
        """Get the indexer URL for current network."""
        return self._ENDPOINTS[self.network]["indexer"]

    @property
    def validator_url(self) -> str:
        """Get the validator URL for current network."""
        return self._ENDPOINTS[self.network]["validator"]

    @classmethod
    def from_env(
        cls,
        env: "Environment",
        testnet: bool | None = None,
    ) -> "DYDXConfig":
        """
        Create configuration from environment.

        Args:
            env: Environment object with loaded credentials.
            testnet: Override testnet setting (uses env default if None).

        Returns:
            DYDXConfig instance.
        """
        is_testnet = testnet if testnet is not None else env.dydx_testnet
        return cls(
            wallet_address=env.dydx.wallet_address,
            mnemonic=env.dydx.mnemonic,
            is_testnet=is_testnet,
        )

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate the configuration.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors: list[str] = []

        if not self.wallet_address:
            errors.append("dYdX: Wallet address is required")

        # Mnemonic required for execution on testnet
        if self.is_testnet and not self.mnemonic:
            errors.append("dYdX: Mnemonic is required for testnet execution")

        # Security warning for mainnet with mnemonic
        if not self.is_testnet and self.mnemonic:
            errors.append(
                "dYdX: SECURITY WARNING - Do not use mnemonic for mainnet! "
                "Use hardware wallet instead."
            )

        return len(errors) == 0, errors

    def to_data_client_config(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader DYDXDataClientConfig dict.

        Returns:
            Dictionary suitable for DYDXDataClientConfig initialization.
        """
        return {
            "wallet_address": self.wallet_address,
            "is_testnet": self.is_testnet,
        }

    def to_exec_client_config(self) -> dict[str, Any]:
        """
        Convert to NautilusTrader DYDXExecClientConfig dict.

        Returns:
            Dictionary suitable for DYDXExecClientConfig initialization.
        """
        return {
            "wallet_address": self.wallet_address,
            "mnemonic": self.mnemonic,
            "is_testnet": self.is_testnet,
            "subaccount_number": self.subaccount_number,
        }


def create_exchange_configs(
    env: "Environment",
    exchanges: list[str] | None = None,
    testnet: bool | None = None,
) -> dict[str, ExchangeConfig | DYDXConfig]:
    """
    Create exchange configurations for multiple exchanges.

    This is a convenience function that creates configurations for
    all specified exchanges from environment variables.

    Args:
        env: Environment object with loaded credentials.
        exchanges: List of exchange names to configure. If None, configures
                   all exchanges with valid credentials.
        testnet: Override testnet setting for all exchanges.

    Returns:
        Dictionary mapping exchange names to their configurations.

    Example:
        >>> env = load_environment()
        >>> configs = create_exchange_configs(env, ["binance", "bybit"], testnet=True)
        >>> binance_config = configs["binance"]
    """
    configs: dict[str, ExchangeConfig | DYDXConfig] = {}

    # Use provided list or auto-detect from environment
    exchange_list = exchanges if exchanges is not None else env.get_enabled_exchanges()

    for exchange in exchange_list:
        exchange_lower = exchange.lower()

        if exchange_lower == "binance" and env.binance.is_valid():
            configs["binance"] = BinanceConfig.from_env(env, testnet=testnet)
        elif exchange_lower == "bybit" and env.bybit.is_valid():
            configs["bybit"] = BybitConfig.from_env(env, testnet=testnet)
        elif exchange_lower == "okx" and env.okx.is_valid():
            configs["okx"] = OKXConfig.from_env(env, testnet=testnet)
        elif exchange_lower == "dydx" and env.dydx.is_dydx_valid():
            configs["dydx"] = DYDXConfig.from_env(env, testnet=testnet)

    return configs
