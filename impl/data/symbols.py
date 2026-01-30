"""
Symbol and Instrument ID utilities for NautilusTrader.

This module provides utilities for creating, parsing, and normalizing
instrument identifiers across multiple exchanges.

Supported Exchanges:
    - Binance (Spot, USDT-M Futures, Coin-M Futures)
    - Bybit (Unified, Contract)
    - OKX (Swap, Futures)
    - dYdX (Perpetuals)

Example:
    >>> from impl.data.symbols import InstrumentIdBuilder, ExchangeVenue
    >>> builder = InstrumentIdBuilder()
    >>> instrument_id = builder.build("BTCUSDT", ExchangeVenue.BINANCE_FUTURES)
    >>> print(instrument_id)  # "BTCUSDT-PERP.BINANCE"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ExchangeVenue(str, Enum):
    """
    Supported exchange venues with NautilusTrader venue identifiers.

    Attributes:
        BINANCE: Binance spot trading.
        BINANCE_FUTURES: Binance USDT-margined perpetual futures.
        BINANCE_COIN_FUTURES: Binance coin-margined inverse futures.
        BYBIT: Bybit unified trading.
        BYBIT_CONTRACT: Bybit legacy contract trading.
        OKX: OKX swap/perpetual trading.
        DYDX: dYdX perpetual trading.
    """

    BINANCE = "BINANCE"
    BINANCE_FUTURES = "BINANCE_FUTURES"
    BINANCE_COIN_FUTURES = "BINANCE_COIN_FUTURES"
    BYBIT = "BYBIT"
    BYBIT_CONTRACT = "BYBIT_CONTRACT"
    OKX = "OKX"
    DYDX = "DYDX"

    @property
    def nautilus_venue(self) -> str:
        """Get the NautilusTrader venue identifier."""
        # NautilusTrader uses simplified venue names
        mapping = {
            ExchangeVenue.BINANCE: "BINANCE",
            ExchangeVenue.BINANCE_FUTURES: "BINANCE",
            ExchangeVenue.BINANCE_COIN_FUTURES: "BINANCE",
            ExchangeVenue.BYBIT: "BYBIT",
            ExchangeVenue.BYBIT_CONTRACT: "BYBIT",
            ExchangeVenue.OKX: "OKX",
            ExchangeVenue.DYDX: "DYDX",
        }
        return mapping.get(self, self.value)

    @property
    def tardis_name(self) -> str:
        """Get the Tardis exchange name for this venue."""
        mapping = {
            ExchangeVenue.BINANCE: "binance",
            ExchangeVenue.BINANCE_FUTURES: "binance-futures",
            ExchangeVenue.BINANCE_COIN_FUTURES: "binance-delivery",
            ExchangeVenue.BYBIT: "bybit",
            ExchangeVenue.BYBIT_CONTRACT: "bybit",
            ExchangeVenue.OKX: "okex-swap",
            ExchangeVenue.DYDX: "dydx",
        }
        return mapping.get(self, self.value.lower())

    @classmethod
    def from_tardis_name(cls, name: str) -> "ExchangeVenue":
        """
        Create ExchangeVenue from Tardis exchange name.

        Args:
            name: Tardis exchange identifier.

        Returns:
            Corresponding ExchangeVenue.

        Raises:
            ValueError: If exchange name is not recognized.
        """
        mapping = {
            "binance": cls.BINANCE,
            "binance-futures": cls.BINANCE_FUTURES,
            "binance-delivery": cls.BINANCE_COIN_FUTURES,
            "bybit": cls.BYBIT,
            "okex-swap": cls.OKX,
            "okex-futures": cls.OKX,
            "dydx": cls.DYDX,
        }
        if name.lower() not in mapping:
            raise ValueError(f"Unknown Tardis exchange: {name}")
        return mapping[name.lower()]


@dataclass(frozen=True)
class InstrumentSpec:
    """
    Specification for a trading instrument.

    Attributes:
        base_currency: Base currency symbol (e.g., "BTC").
        quote_currency: Quote currency symbol (e.g., "USDT").
        venue: Exchange venue.
        instrument_type: Type of instrument (SPOT, PERP, FUTURE).
        expiry: Expiry date for futures (e.g., "240329" for March 29, 2024).
    """

    base_currency: str
    quote_currency: str
    venue: ExchangeVenue
    instrument_type: str = "PERP"
    expiry: str | None = None

    @property
    def raw_symbol(self) -> str:
        """Get the raw exchange symbol."""
        symbol = f"{self.base_currency}{self.quote_currency}"
        if self.expiry:
            symbol = f"{symbol}_{self.expiry}"
        return symbol

    @property
    def instrument_id(self) -> str:
        """Get the NautilusTrader instrument ID string."""
        suffix = ""
        if self.instrument_type == "PERP":
            suffix = "-PERP"
        elif self.instrument_type == "FUTURE" and self.expiry:
            suffix = f"-{self.expiry}"
        return f"{self.raw_symbol}{suffix}.{self.venue.nautilus_venue}"


class InstrumentIdBuilder:
    """
    Builder for creating NautilusTrader instrument IDs.

    This class provides a fluent interface for constructing instrument
    identifiers from various input formats.

    Example:
        >>> builder = InstrumentIdBuilder()
        >>> # From raw symbol
        >>> id1 = builder.build("BTCUSDT", ExchangeVenue.BINANCE_FUTURES)
        >>> # From specification
        >>> spec = InstrumentSpec("BTC", "USDT", ExchangeVenue.BINANCE_FUTURES)
        >>> id2 = builder.from_spec(spec)
    """

    # Pattern for parsing raw symbols
    _SYMBOL_PATTERNS = [
        # Standard pairs: BTCUSDT, ETHBTC
        re.compile(r"^(?P<base>[A-Z0-9]+)(?P<quote>USDT|BUSD|USDC|USD|BTC|ETH|EUR)$"),
        # Futures with expiry: BTCUSDT_240329
        re.compile(
            r"^(?P<base>[A-Z0-9]+)(?P<quote>USDT|USD)_(?P<expiry>\d{6})$"
        ),
        # dYdX format: BTC-USD
        re.compile(r"^(?P<base>[A-Z0-9]+)-(?P<quote>USD)$"),
    ]

    def __init__(self) -> None:
        """Initialize the builder."""
        self._venue_prefixes: dict[ExchangeVenue, str] = {
            ExchangeVenue.BINANCE_FUTURES: "-PERP",
            ExchangeVenue.BINANCE_COIN_FUTURES: "-PERP",  # Inverse futures
            ExchangeVenue.OKX: "-PERP",
            ExchangeVenue.DYDX: "-PERP",
            ExchangeVenue.BYBIT: "-PERP",
        }

    def build(
        self,
        symbol: str,
        venue: ExchangeVenue,
        instrument_type: str | None = None,
    ) -> str:
        """
        Build an instrument ID from a raw symbol.

        Args:
            symbol: Raw exchange symbol (e.g., "BTCUSDT").
            venue: Exchange venue.
            instrument_type: Override instrument type (SPOT, PERP, FUTURE).

        Returns:
            NautilusTrader instrument ID string.

        Example:
            >>> builder = InstrumentIdBuilder()
            >>> builder.build("BTCUSDT", ExchangeVenue.BINANCE_FUTURES)
            'BTCUSDT-PERP.BINANCE'
        """
        # Normalize symbol
        symbol = symbol.upper().strip()

        # Determine instrument type suffix
        if instrument_type is None:
            # Default based on venue - check futures venues first
            if venue in self._venue_prefixes:
                suffix = self._venue_prefixes[venue]
            else:
                suffix = ""
        else:
            suffix = f"-{instrument_type}" if instrument_type != "SPOT" else ""

        return f"{symbol}{suffix}.{venue.nautilus_venue}"

    def from_spec(self, spec: InstrumentSpec) -> str:
        """
        Build an instrument ID from a specification.

        Args:
            spec: Instrument specification.

        Returns:
            NautilusTrader instrument ID string.
        """
        return spec.instrument_id

    def parse(self, symbol: str) -> tuple[str, str] | None:
        """
        Parse a raw symbol into base and quote currencies.

        Args:
            symbol: Raw symbol to parse.

        Returns:
            Tuple of (base, quote) or None if parsing fails.
        """
        for pattern in self._SYMBOL_PATTERNS:
            match = pattern.match(symbol.upper())
            if match:
                return match.group("base"), match.group("quote")
        return None


@dataclass
class SymbolMapper:
    """
    Maps symbols between different exchange formats.

    This class handles the conversion of symbols between:
    - Raw exchange format (e.g., "BTCUSDT")
    - NautilusTrader format (e.g., "BTCUSDT-PERP.BINANCE")
    - Tardis format (e.g., "btcusdt" for binance-futures)

    Attributes:
        venue: Exchange venue for this mapper.
        custom_mappings: Custom symbol mappings.
    """

    venue: ExchangeVenue
    custom_mappings: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Initialize default mappings for specific venues."""
        # dYdX uses different symbol format
        if self.venue == ExchangeVenue.DYDX:
            self.custom_mappings.update({
                "BTCUSD": "BTC-USD",
                "ETHUSD": "ETH-USD",
                "SOLUSD": "SOL-USD",
            })

    def to_nautilus(self, raw_symbol: str) -> str:
        """
        Convert raw exchange symbol to NautilusTrader format.

        Args:
            raw_symbol: Raw exchange symbol.

        Returns:
            NautilusTrader instrument ID.
        """
        symbol = raw_symbol.upper()

        # Check custom mappings
        if symbol in self.custom_mappings:
            symbol = self.custom_mappings[symbol]

        builder = InstrumentIdBuilder()
        return builder.build(symbol, self.venue)

    def to_tardis(self, raw_symbol: str) -> str:
        """
        Convert raw exchange symbol to Tardis format.

        Args:
            raw_symbol: Raw exchange symbol.

        Returns:
            Tardis symbol format.
        """
        # Tardis generally uses lowercase
        return raw_symbol.lower()

    def from_nautilus(self, instrument_id: str) -> str:
        """
        Extract raw symbol from NautilusTrader instrument ID.

        Args:
            instrument_id: NautilusTrader instrument ID.

        Returns:
            Raw exchange symbol.
        """
        parsed = parse_instrument_id(instrument_id)
        return parsed.get("raw_symbol", instrument_id.split(".")[0])


def normalize_symbol(symbol: str, venue: ExchangeVenue | None = None) -> str:
    """
    Normalize a symbol to standard format.

    Args:
        symbol: Raw symbol in any format.
        venue: Optional venue for venue-specific normalization.

    Returns:
        Normalized symbol string.

    Example:
        >>> normalize_symbol("btc-usdt")
        'BTCUSDT'
        >>> normalize_symbol("BTC/USDT")
        'BTCUSDT'
    """
    # Remove common separators and normalize
    normalized = symbol.upper()
    normalized = normalized.replace("-", "").replace("/", "").replace("_", "")

    # dYdX specific
    if venue == ExchangeVenue.DYDX:
        # Keep the dash format for dYdX
        parts = symbol.upper().replace("/", "-").split("-")
        if len(parts) == 2:
            normalized = f"{parts[0]}-{parts[1]}"

    return normalized


def parse_instrument_id(instrument_id: str) -> dict[str, Any]:
    """
    Parse a NautilusTrader instrument ID into components.

    Args:
        instrument_id: NautilusTrader instrument ID string.

    Returns:
        Dictionary with parsed components:
            - raw_symbol: Symbol without suffix
            - instrument_type: SPOT, PERP, or FUTURE
            - venue: Exchange venue name
            - expiry: Expiry date if applicable

    Example:
        >>> parse_instrument_id("BTCUSDT-PERP.BINANCE")
        {'raw_symbol': 'BTCUSDT', 'instrument_type': 'PERP', 'venue': 'BINANCE', 'expiry': None}
    """
    if "." not in instrument_id:
        return {"raw_symbol": instrument_id, "instrument_type": "UNKNOWN", "venue": "", "expiry": None}

    symbol_part, venue = instrument_id.rsplit(".", 1)

    # Check for instrument type suffix
    if "-PERP" in symbol_part:
        raw_symbol = symbol_part.replace("-PERP", "")
        instrument_type = "PERP"
        expiry = None
    elif "-" in symbol_part:
        # Could be future with expiry
        parts = symbol_part.rsplit("-", 1)
        if len(parts[1]) == 6 and parts[1].isdigit():
            raw_symbol = parts[0]
            instrument_type = "FUTURE"
            expiry = parts[1]
        else:
            raw_symbol = symbol_part
            instrument_type = "SPOT"
            expiry = None
    else:
        raw_symbol = symbol_part
        instrument_type = "SPOT"
        expiry = None

    return {
        "raw_symbol": raw_symbol,
        "instrument_type": instrument_type,
        "venue": venue,
        "expiry": expiry,
    }


def create_instrument_specs(
    symbols: list[str],
    venue: ExchangeVenue,
    instrument_type: str = "PERP",
) -> list[InstrumentSpec]:
    """
    Create instrument specifications from a list of symbols.

    Args:
        symbols: List of raw symbols (e.g., ["BTCUSDT", "ETHUSDT"]).
        venue: Exchange venue.
        instrument_type: Type of instrument.

    Returns:
        List of InstrumentSpec objects.
    """
    builder = InstrumentIdBuilder()
    specs = []

    for symbol in symbols:
        parsed = builder.parse(symbol)
        if parsed:
            base, quote = parsed
            specs.append(
                InstrumentSpec(
                    base_currency=base,
                    quote_currency=quote,
                    venue=venue,
                    instrument_type=instrument_type,
                )
            )
        else:
            # Fallback: assume USDT quote
            specs.append(
                InstrumentSpec(
                    base_currency=symbol.replace("USDT", ""),
                    quote_currency="USDT",
                    venue=venue,
                    instrument_type=instrument_type,
                )
            )

    return specs
