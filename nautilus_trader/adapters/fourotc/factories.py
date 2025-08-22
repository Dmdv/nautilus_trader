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

"""Factory for 4OTC live data clients."""

import asyncio

from nautilus_trader.adapters.fourotc.config import FourOTCDataClientConfig
from nautilus_trader.adapters.fourotc.data import FourOTCDataClient
from nautilus_trader.adapters.fourotc.providers import FourOTCInstrumentProvider
from nautilus_trader.common.component import LiveClock, MessageBus
from nautilus_trader.common.config import InstrumentProviderConfig
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.live.factories import LiveDataClientFactory


class FourOTCLiveDataClientFactory(LiveDataClientFactory):
    """Factory for 4OTC live data clients."""

    @staticmethod
    def create(
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: FourOTCDataClientConfig,
        msgbus: MessageBus,
        cache: Any,
        clock: LiveClock,
    ) -> FourOTCDataClient:
        """
        Create a 4OTC live data client.
        
        Parameters
        ----------
        loop : asyncio.AbstractEventLoop
            The event loop for the client.
        name : str
            The client name.
        config : FourOTCDataClientConfig
            The configuration for the client.
        msgbus : MessageBus
            The message bus for the client.
        cache : Cache
            The cache for the client.
        clock : LiveClock
            The clock for the client.
            
        Returns
        -------
        FourOTCDataClient
            The created client.
        """
        # Create instrument provider
        provider_config = config.instrument_provider or InstrumentProviderConfig()
        instrument_provider = FourOTCInstrumentProvider()
        
        # Load instruments if configured to do so
        if provider_config.load_all:
            instrument_provider.load_all(filters=provider_config.filters)
        elif provider_config.load_ids:
            # Load specific instruments by IDs if configured
            pass  # Not implemented for 4OTC yet

        # Create and return the data client
        return FourOTCDataClient(
            loop=loop,
            client_id=name,
            config=config,
            instrument_provider=instrument_provider,
        )