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

"""Data client for 4OTC market data via NATS."""

import asyncio
import json
from typing import Any, Dict, List, Optional

import nats
from nats.aio.client import Client as NATSClient

from nautilus_trader.adapters.fourotc.config import FourOTCDataClientConfig
from nautilus_trader.adapters.fourotc.core import FOUROTC_VENUE
from nautilus_trader.adapters.fourotc.providers import FourOTCInstrumentProvider
from nautilus_trader.common.enums import LogLevel
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.data.messages import DataRequest
from nautilus_trader.data.messages import DataResponse
from nautilus_trader.data.messages import SubscribeOrderBook
from nautilus_trader.data.messages import SubscribeQuoteTicks
from nautilus_trader.data.messages import SubscribeTradeTicks
from nautilus_trader.data.messages import UnsubscribeOrderBook
from nautilus_trader.data.messages import UnsubscribeQuoteTicks
from nautilus_trader.data.messages import UnsubscribeTradeTicks
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.data import QuoteTick, TradeTick
from nautilus_trader.model.data import OrderBookDelta, OrderBookDeltas
from nautilus_trader.model.enums import AggressorSide, BookAction, OrderSide
from nautilus_trader.model.identifiers import InstrumentId, TradeId
from nautilus_trader.model.objects import Price, Quantity


class FourOTCDataClient(LiveMarketDataClient):
    """
    Provides a data client for 4OTC market data via NATS messaging.
    
    This client connects to a NATS server that receives market data from the 4OTC
    market data adapter and converts it to Nautilus data types.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        client_id: str,
        config: FourOTCDataClientConfig,
        instrument_provider: FourOTCInstrumentProvider,
    ) -> None:
        PyCondition.not_none(instrument_provider, "instrument_provider")
        
        super().__init__(
            loop=loop,
            client_id=client_id,
            venue=FOUROTC_VENUE,
            instrument_provider=instrument_provider,
            config=config,
        )

        self._config = config
        self._instrument_provider = instrument_provider
        self._nats_client: Optional[NATSClient] = None
        self._subscriptions: Dict[str, int] = {}  # subject -> subscription_id

    async def _connect(self) -> None:
        """Connect to the NATS server."""
        try:
            self._nats_client = await nats.connect(
                servers=[self._config.nats_url],
                connect_timeout=self._config.nats_connection_timeout,
                max_reconnect_attempts=self._config.nats_reconnect_attempts,
                reconnect_time_wait=self._config.nats_max_reconnect_wait,
                error_cb=self._on_nats_error,
                closed_cb=self._on_nats_closed,
                reconnected_cb=self._on_nats_reconnected,
            )
            self._log.info(f"Connected to NATS server at {self._config.nats_url}")
        except Exception as e:
            self._log.error(f"Failed to connect to NATS: {e}")
            raise

    async def _disconnect(self) -> None:
        """Disconnect from the NATS server."""
        if self._nats_client and not self._nats_client.is_closed:
            await self._nats_client.close()
            self._log.info("Disconnected from NATS server")

    async def _on_nats_error(self, error: Exception) -> None:
        """Handle NATS connection errors."""
        self._log.error(f"NATS connection error: {error}")

    async def _on_nats_closed(self) -> None:
        """Handle NATS connection closed."""
        self._log.warning("NATS connection closed")

    async def _on_nats_reconnected(self) -> None:
        """Handle NATS reconnection."""
        self._log.info("NATS connection reconnected")

    async def _subscribe_trade_ticks(self, command: SubscribeTradeTicks) -> None:
        """
        Subscribe to trade ticks for an instrument.
        
        Parameters
        ----------
        command : SubscribeTradeTicks
            The subscription command.
        """
        if not self._nats_client:
            self._log.error("Cannot subscribe: NATS client not connected")
            return

        # Extract security_id from instrument metadata or mapping
        security_id = self._get_security_id_for_instrument(command.instrument_id)
        if security_id is None:
            self._log.error(f"No security ID mapping for {command.instrument_id}")
            return

        # Subscribe to trade messages for this security
        subject = f"{self._config.nats_subject_prefix}.trades.*.{security_id}"
        
        try:
            subscription = await self._nats_client.subscribe(
                subject,
                cb=lambda msg: asyncio.create_task(self._handle_trade_message(msg, command.instrument_id))
            )
            self._subscriptions[subject] = subscription.id
            self._log.info(f"Subscribed to trades for {command.instrument_id} on subject {subject}")
        except Exception as e:
            self._log.error(f"Failed to subscribe to trades for {command.instrument_id}: {e}")

    async def _unsubscribe_trade_ticks(self, command: UnsubscribeTradeTicks) -> None:
        """
        Unsubscribe from trade ticks for an instrument.
        
        Parameters
        ----------
        command : UnsubscribeTradeTicks
            The unsubscription command.
        """
        if not self._nats_client:
            return

        security_id = self._get_security_id_for_instrument(command.instrument_id)
        if security_id is None:
            return

        subject = f"{self._config.nats_subject_prefix}.trades.*.{security_id}"
        subscription_id = self._subscriptions.pop(subject, None)
        
        if subscription_id is not None:
            try:
                await self._nats_client.unsubscribe(subscription_id)
                self._log.info(f"Unsubscribed from trades for {command.instrument_id}")
            except Exception as e:
                self._log.error(f"Failed to unsubscribe from trades for {command.instrument_id}: {e}")

    async def _subscribe_order_book_deltas(self, command: SubscribeOrderBook) -> None:
        """
        Subscribe to order book deltas for an instrument.
        
        Parameters
        ----------
        command : SubscribeOrderBook
            The subscription command.
        """
        if not self._nats_client:
            self._log.error("Cannot subscribe: NATS client not connected")
            return

        security_id = self._get_security_id_for_instrument(command.instrument_id)
        if security_id is None:
            self._log.error(f"No security ID mapping for {command.instrument_id}")
            return

        # Subscribe to order book snapshot messages for this security
        subject = f"{self._config.nats_subject_prefix}.snapshot.level2.*.{security_id}"
        
        try:
            subscription = await self._nats_client.subscribe(
                subject,
                cb=lambda msg: asyncio.create_task(self._handle_orderbook_message(msg, command.instrument_id))
            )
            self._subscriptions[subject] = subscription.id
            self._log.info(f"Subscribed to order book for {command.instrument_id} on subject {subject}")
        except Exception as e:
            self._log.error(f"Failed to subscribe to order book for {command.instrument_id}: {e}")

    async def _unsubscribe_order_book_deltas(self, command: UnsubscribeOrderBook) -> None:
        """
        Unsubscribe from order book deltas for an instrument.
        
        Parameters
        ----------
        command : UnsubscribeOrderBook
            The unsubscription command.
        """
        if not self._nats_client:
            return

        security_id = self._get_security_id_for_instrument(command.instrument_id)
        if security_id is None:
            return

        subject = f"{self._config.nats_subject_prefix}.snapshot.level2.*.{security_id}"
        subscription_id = self._subscriptions.pop(subject, None)
        
        if subscription_id is not None:
            try:
                await self._nats_client.unsubscribe(subscription_id)
                self._log.info(f"Unsubscribed from order book for {command.instrument_id}")
            except Exception as e:
                self._log.error(f"Failed to unsubscribe from order book for {command.instrument_id}: {e}")

    async def _handle_trade_message(self, msg: Any, instrument_id: InstrumentId) -> None:
        """
        Handle incoming trade message from NATS.
        
        Parameters
        ----------
        msg : nats.aio.msg.Msg
            The NATS message.
        instrument_id : InstrumentId
            The instrument identifier.
        """
        try:
            # Decode JSON message
            data = json.loads(msg.data.decode())
            
            # Convert to TradeTick
            trade_tick = TradeTick(
                instrument_id=instrument_id,
                price=Price.from_str(str(data["price"])),
                size=Quantity.from_str(str(data["quantity"])),
                aggressor_side=AggressorSide.BUYER if data.get("aggressor_side") == "buy" else AggressorSide.SELLER,
                trade_id=TradeId(str(data.get("trade_id", ""))),
                ts_event=millis_to_nanos(data.get("timestamp", 0)),
                ts_init=self._clock.timestamp_ns(),
            )
            
            self._handle_data(trade_tick)
            
        except Exception as e:
            self._log.error(f"Error processing trade message for {instrument_id}: {e}")

    async def _handle_orderbook_message(self, msg: Any, instrument_id: InstrumentId) -> None:
        """
        Handle incoming order book message from NATS.
        
        Parameters
        ----------
        msg : nats.aio.msg.Msg
            The NATS message.
        instrument_id : InstrumentId
            The instrument identifier.
        """
        try:
            # Decode JSON message
            data = json.loads(msg.data.decode())
            
            # Convert order book entries to deltas
            deltas = []
            ts_event = millis_to_nanos(data.get("timestamp", 0))
            ts_init = self._clock.timestamp_ns()
            
            # Process bid and ask entries
            for bid in data.get("bids", []):
                delta = OrderBookDelta(
                    instrument_id=instrument_id,
                    action=BookAction.UPDATE,
                    order=None,  # No specific order for snapshot
                    side=OrderSide.BUY,
                    price=Price.from_str(str(bid["price"])),
                    size=Quantity.from_str(str(bid["quantity"])),
                    order_id=0,
                    flags=0,
                    sequence=0,
                    ts_event=ts_event,
                    ts_init=ts_init,
                )
                deltas.append(delta)
                
            for ask in data.get("asks", []):
                delta = OrderBookDelta(
                    instrument_id=instrument_id,
                    action=BookAction.UPDATE,
                    order=None,  # No specific order for snapshot
                    side=OrderSide.SELL,
                    price=Price.from_str(str(ask["price"])),
                    size=Quantity.from_str(str(ask["quantity"])),
                    order_id=0,
                    flags=0,
                    sequence=0,
                    ts_event=ts_event,
                    ts_init=ts_init,
                )
                deltas.append(delta)
            
            if deltas:
                order_book_deltas = OrderBookDeltas(
                    instrument_id=instrument_id,
                    deltas=deltas,
                    is_snapshot=True,
                    sequence=0,
                    ts_event=ts_event,
                    ts_init=ts_init,
                )
                self._handle_data(order_book_deltas)
                
        except Exception as e:
            self._log.error(f"Error processing order book message for {instrument_id}: {e}")

    def _get_security_id_for_instrument(self, instrument_id: InstrumentId) -> Optional[int]:
        """
        Get the 4OTC security ID for a Nautilus instrument ID.
        
        Parameters
        ----------
        instrument_id : InstrumentId
            The Nautilus instrument identifier.
            
        Returns
        -------
        int or None
            The 4OTC security ID if found, otherwise None.
        """
        # Simple mapping based on symbol
        symbol_str = str(instrument_id.symbol)
        if symbol_str == "BTC/USDT":
            return 109
        elif symbol_str == "ETH/USDT":
            return 110
        elif symbol_str == "BTC/USDT-PERP":
            return 277
        return None