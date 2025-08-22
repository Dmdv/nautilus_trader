# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2025 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------

"""Instrument provider for 4OTC."""

import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional

from nautilus_trader.adapters.fourotc.core import FOUROTC_VENUE, SECURITY_MAPPING, VENUE_MAPPING
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.core.data import Data
from nautilus_trader.model.currencies import USD, USDT
from nautilus_trader.model.enums import AssetClass, AssetType, CurrencyType
from nautilus_trader.model.identifiers import InstrumentId, Symbol
from nautilus_trader.model.instruments import CryptoFuture, CryptoPerpetual, CurrencyPair
from nautilus_trader.model.objects import Currency, Money, Price, Quantity


class FourOTCInstrumentProvider:
    """
    Provides instrument definitions for 4OTC market data.
    
    This provider creates Nautilus instrument objects based on 4OTC security definitions
    and venue mappings from the SBE protocol.
    """

    def __init__(self) -> None:
        self._instruments: Dict[InstrumentId, Any] = {}
        self._security_to_instrument: Dict[int, InstrumentId] = {}
        self._venue_to_instruments: Dict[int, List[InstrumentId]] = {}

    async def load_all_async(self, filters: Optional[Dict] = None) -> None:
        """
        Load all supported instruments from 4OTC.
        
        Parameters
        ----------
        filters : dict, optional
            Instrument filters (not used for 4OTC).
        """
        # Create instruments based on known security and venue mappings
        self._create_default_instruments()

    def load_all(self, filters: Optional[Dict] = None) -> None:
        """
        Load all supported instruments from 4OTC synchronously.
        
        Parameters
        ----------
        filters : dict, optional
            Instrument filters (not used for 4OTC).
        """
        asyncio.run(self.load_all_async(filters))

    def get_all(self) -> List[Any]:
        """
        Return all loaded instruments.
        
        Returns
        -------
        list[Instrument]
            All loaded instruments.
        """
        return list(self._instruments.values())

    def find(self, instrument_id: InstrumentId) -> Optional[Any]:
        """
        Find an instrument by its identifier.
        
        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument identifier.
            
        Returns
        -------
        Instrument or None
            The instrument if found, otherwise None.
        """
        return self._instruments.get(instrument_id)

    def get_by_security_id(self, security_id: int) -> Optional[Any]:
        """
        Get an instrument by its 4OTC security ID.
        
        Parameters
        ----------
        security_id : int
            The 4OTC security ID.
            
        Returns
        -------
        Instrument or None
            The instrument if found, otherwise None.
        """
        instrument_id = self._security_to_instrument.get(security_id)
        if instrument_id:
            return self._instruments.get(instrument_id)
        return None

    def get_by_venue_id(self, venue_id: int) -> List[Any]:
        """
        Get all instruments for a specific venue ID.
        
        Parameters
        ----------
        venue_id : int
            The 4OTC venue ID.
            
        Returns
        -------
        list[Instrument]
            All instruments for the venue.
        """
        instrument_ids = self._venue_to_instruments.get(venue_id, [])
        return [self._instruments[instrument_id] for instrument_id in instrument_ids]

    def _create_default_instruments(self) -> None:
        """Create default instruments based on known mappings."""
        
        # BTC/USDT on Binance Spot (venue 28, security 109)
        btc_usdt_spot = CurrencyPair(
            id=InstrumentId(Symbol("BTC/USDT"), FOUROTC_VENUE),
            raw_symbol=Symbol("BTC/USDT"),
            base_currency=Currency.from_str("BTC"),
            quote_currency=USDT,
            price_precision=2,
            size_precision=6,
            price_increment=Price.from_str("0.01"),
            size_increment=Quantity.from_str("0.000001"),
            lot_size=None,
            max_quantity=Quantity.from_str("10000"),
            min_quantity=Quantity.from_str("0.000001"),
            max_notional=Money(100_000_000, USDT),
            min_notional=Money(10, USDT),
            max_price=Price.from_str("1000000"),
            min_price=Price.from_str("0.01"),
            ts_event=0,
            ts_init=0,
            margin_init=Decimal("0"),
            margin_maint=Decimal("0"),
            maker_fee=Decimal("0.001"),
            taker_fee=Decimal("0.001"),
        )
        
        # ETH/USDT on OKX Spot (venue 54, security 110)  
        eth_usdt_spot = CurrencyPair(
            id=InstrumentId(Symbol("ETH/USDT"), FOUROTC_VENUE),
            raw_symbol=Symbol("ETH/USDT"),
            base_currency=Currency.from_str("ETH"),
            quote_currency=USDT,
            price_precision=2,
            size_precision=6,
            price_increment=Price.from_str("0.01"),
            size_increment=Quantity.from_str("0.000001"),
            lot_size=None,
            max_quantity=Quantity.from_str("10000"),
            min_quantity=Quantity.from_str("0.000001"),
            max_notional=Money(10_000_000, USDT),
            min_notional=Money(10, USDT),
            max_price=Price.from_str("100000"),
            min_price=Price.from_str("0.01"),
            ts_event=0,
            ts_init=0,
            margin_init=Decimal("0"),
            margin_maint=Decimal("0"),
            maker_fee=Decimal("0.001"),
            taker_fee=Decimal("0.001"),
        )
        
        # BTC/USDT Perpetual on Binance Futures (venue 34, security 277)
        btc_usdt_perp = CryptoPerpetual(
            id=InstrumentId(Symbol("BTC/USDT-PERP"), FOUROTC_VENUE),
            raw_symbol=Symbol("BTC/USDT-PERP"),
            base_currency=Currency.from_str("BTC"),
            quote_currency=USDT,
            settlement_currency=USDT,
            is_inverse=False,
            price_precision=1,
            size_precision=3,
            price_increment=Price.from_str("0.1"),
            size_increment=Quantity.from_str("0.001"),
            lot_size=None,
            max_quantity=Quantity.from_str("1000"),
            min_quantity=Quantity.from_str("0.001"),
            max_notional=Money(10_000_000, USDT),
            min_notional=Money(5, USDT),
            max_price=Price.from_str("1000000"),
            min_price=Price.from_str("0.1"),
            ts_event=0,
            ts_init=0,
            margin_init=Decimal("0.02"),
            margin_maint=Decimal("0.01"),
            maker_fee=Decimal("0.0002"),
            taker_fee=Decimal("0.0004"),
        )

        # Store instruments
        self._instruments[btc_usdt_spot.id] = btc_usdt_spot
        self._instruments[eth_usdt_spot.id] = eth_usdt_spot
        self._instruments[btc_usdt_perp.id] = btc_usdt_perp

        # Store security ID mappings
        self._security_to_instrument[109] = btc_usdt_spot.id  # BTC/USDT spot
        self._security_to_instrument[110] = eth_usdt_spot.id  # ETH/USDT spot
        self._security_to_instrument[277] = btc_usdt_perp.id  # BTC/USDT perp

        # Store venue ID mappings
        self._venue_to_instruments[28] = [btc_usdt_spot.id]  # Binance Spot
        self._venue_to_instruments[34] = [btc_usdt_perp.id]  # Binance Futures USDM
        self._venue_to_instruments[54] = [eth_usdt_spot.id]  # OKX Spot