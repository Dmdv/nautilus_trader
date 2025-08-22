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

"""Core constants and types for the 4OTC adapter."""

from nautilus_trader.model.identifiers import Venue

# 4OTC Exchange venue identifier
FOUROTC_VENUE = Venue("FOUROTC")

# Supported Venue IDs from 4OTC protocol
VENUE_MAPPING = {
    28: "BINANCE_SPOT",
    34: "BINANCE_FUTURES_USDM", 
    35: "BINANCE_FUTURES_COINM",
    54: "OKX_SPOT",
}

# Major Security IDs 
SECURITY_MAPPING = {
    109: "BTC/USDT",
    110: "ETH/USDT", 
    277: "BTC/USDT-PERP",
}

# SBE Template IDs to message types
SBE_TEMPLATE_MAPPING = {
    0: "Heartbeat",
    1: "MarketDataRequestReject",
    2: "MarketDataRequestSnapshotLevelTwo", 
    3: "MarketDataRequestTrades",
    4: "MarketDataSnapshotFullRefreshLevelTwo",
    5: "MarketDataIncrementalRefreshTrades",
    6: "SecurityStatus",
    7: "SecurityDefinitionRequest",
    8: "SecurityDefinition",
    10: "UnsequencedHeartbeat",
    11: "MarketDataRequestAccept",
    14: "ClientDisconnectRequest",
    15: "MarketDataSnapshotFullRefreshLevelTwoWithScaling",
    16: "MarketDataIncrementalRefreshTradesWithScaling", 
    17: "SecurityDefinitionExtension",
}