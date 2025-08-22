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

"""Configuration for 4OTC adapter."""

from typing import Optional

import msgspec

from nautilus_trader.common.config import LiveDataClientConfig


class FourOTCDataClientConfig(LiveDataClientConfig, frozen=True):
    """
    Configuration for ``FourOTCDataClient`` instances.
    
    Parameters
    ----------
    nats_url : str, optional
        The NATS server URL to subscribe to 4OTC market data.
        Default is "nats://127.0.0.1:4222".
    nats_subject_prefix : str, optional  
        The NATS subject prefix for 4OTC market data streams.
        Default is "marketdata.4otc".
    nats_connection_timeout : float, optional
        The NATS connection timeout in seconds.
        Default is 10.0 seconds.
    nats_reconnect_attempts : int, optional
        The maximum number of NATS reconnection attempts.
        Default is 10.
    nats_max_reconnect_wait : float, optional
        The maximum time to wait between NATS reconnection attempts in seconds.
        Default is 30.0 seconds.
    instrument_provider : InstrumentProviderConfig, optional
        The instrument provider configuration.
    """

    nats_url: str = "nats://127.0.0.1:4222"
    nats_subject_prefix: str = "marketdata.4otc"
    nats_connection_timeout: float = 10.0
    nats_reconnect_attempts: int = 10
    nats_max_reconnect_wait: float = 30.0