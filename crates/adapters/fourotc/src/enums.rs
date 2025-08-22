// -------------------------------------------------------------------------------------------------
//  Copyright (C) 2015-2025 Nautech Systems Pty Ltd. All rights reserved.
//  https://nautechsystems.io
//
//  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
//  You may not use this file except in compliance with the License.
//  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
//
//  Unless required by applicable law or agreed to in writing, software
//  distributed under the License is distributed on an "AS IS" BASIS,
//  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//  See the License for the specific language governing permissions and
//  limitations under the License.
// -------------------------------------------------------------------------------------------------

//! Enumerations for the 4OTC adapter.

use std::{
    fmt::{Display, Formatter},
    str::FromStr,
};

use serde::{Deserialize, Serialize};

/// Connection state of the 4OTC data client
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ConnectionState {
    /// Client is disconnected
    Disconnected,
    /// Client is connecting
    Connecting,
    /// Client is connected and active
    Connected,
    /// Client is reconnecting after a failure
    Reconnecting,
    /// Client connection failed
    Failed,
}

impl Display for ConnectionState {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let state_str = match self {
            Self::Disconnected => "DISCONNECTED",
            Self::Connecting => "CONNECTING",
            Self::Connected => "CONNECTED",
            Self::Reconnecting => "RECONNECTING",
            Self::Failed => "FAILED",
        };
        write!(f, "{}", state_str)
    }
}

/// Subscription state for market data feeds
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SubscriptionState {
    /// Not subscribed
    Unsubscribed,
    /// Subscription is pending
    Pending,
    /// Successfully subscribed
    Subscribed,
    /// Subscription failed
    Failed,
}

impl Display for SubscriptionState {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let state_str = match self {
            Self::Unsubscribed => "UNSUBSCRIBED",
            Self::Pending => "PENDING",
            Self::Subscribed => "SUBSCRIBED",
            Self::Failed => "FAILED",
        };
        write!(f, "{}", state_str)
    }
}

/// Market data message types from 4OTC
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum MessageType {
    /// Heartbeat message
    Heartbeat,
    /// Unsequenced heartbeat
    UnsequencedHeartbeat,
    /// Market data request reject
    RequestReject,
    /// Market data request accept
    RequestAccept,
    /// Order book snapshot (Level 2)
    OrderBookSnapshot,
    /// Order book incremental update
    OrderBookUpdate,
    /// Trade execution
    Trade,
    /// Security definition
    SecurityDefinition,
    /// Security definition extension
    SecurityDefinitionExtension,
    /// Security status update
    SecurityStatus,
    /// Snapshot request
    SnapshotRequest,
    /// Trades request
    TradesRequest,
    /// Security definition request
    SecurityDefinitionRequest,
    /// Client disconnect request
    ClientDisconnectRequest,
    /// Unknown message type
    Unknown,
}

impl Display for MessageType {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let type_str = match self {
            Self::Heartbeat => "HEARTBEAT",
            Self::UnsequencedHeartbeat => "UNSEQUENCED_HEARTBEAT",
            Self::RequestReject => "REQUEST_REJECT",
            Self::RequestAccept => "REQUEST_ACCEPT",
            Self::OrderBookSnapshot => "ORDER_BOOK_SNAPSHOT",
            Self::OrderBookUpdate => "ORDER_BOOK_UPDATE",
            Self::Trade => "TRADE",
            Self::SecurityDefinition => "SECURITY_DEFINITION",
            Self::SecurityDefinitionExtension => "SECURITY_DEFINITION_EXTENSION",
            Self::SecurityStatus => "SECURITY_STATUS",
            Self::SnapshotRequest => "SNAPSHOT_REQUEST",
            Self::TradesRequest => "TRADES_REQUEST",
            Self::SecurityDefinitionRequest => "SECURITY_DEFINITION_REQUEST",
            Self::ClientDisconnectRequest => "CLIENT_DISCONNECT_REQUEST",
            Self::Unknown => "UNKNOWN",
        };
        write!(f, "{}", type_str)
    }
}

impl FromStr for MessageType {
    type Err = anyhow::Error;
    
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "HEARTBEAT" => Ok(Self::Heartbeat),
            "UNSEQUENCED_HEARTBEAT" | "UNSEQUENCEDHEARTBEAT" => Ok(Self::UnsequencedHeartbeat),
            "REQUEST_REJECT" | "REQUESTREJECT" => Ok(Self::RequestReject),
            "REQUEST_ACCEPT" | "REQUESTACCEPT" => Ok(Self::RequestAccept),
            "ORDER_BOOK_SNAPSHOT" | "ORDERBOOKSNAPSHOT" => Ok(Self::OrderBookSnapshot),
            "ORDER_BOOK_UPDATE" | "ORDERBOOKUPDATE" => Ok(Self::OrderBookUpdate),
            "TRADE" => Ok(Self::Trade),
            "SECURITY_DEFINITION" | "SECURITYDEFINITION" => Ok(Self::SecurityDefinition),
            "SECURITY_DEFINITION_EXTENSION" | "SECURITYDEFINITIONEXTENSION" => {
                Ok(Self::SecurityDefinitionExtension)
            }
            "SECURITY_STATUS" | "SECURITYSTATUS" => Ok(Self::SecurityStatus),
            "SNAPSHOT_REQUEST" | "SNAPSHOTREQUEST" => Ok(Self::SnapshotRequest),
            "TRADES_REQUEST" | "TRADESREQUEST" => Ok(Self::TradesRequest),
            "SECURITY_DEFINITION_REQUEST" | "SECURITYDEFINITIONREQUEST" => {
                Ok(Self::SecurityDefinitionRequest)
            }
            "CLIENT_DISCONNECT_REQUEST" | "CLIENTDISCONNECTREQUEST" => {
                Ok(Self::ClientDisconnectRequest)
            }
            "UNKNOWN" => Ok(Self::Unknown),
            _ => Err(anyhow::anyhow!("Unknown message type: {}", s)),
        }
    }
}

/// Order book action types
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum BookAction {
    /// Add a new order to the book
    Add,
    /// Update an existing order
    Update,
    /// Delete an order from the book
    Delete,
    /// Clear the entire book
    Clear,
}

impl Display for BookAction {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let action_str = match self {
            Self::Add => "ADD",
            Self::Update => "UPDATE", 
            Self::Delete => "DELETE",
            Self::Clear => "CLEAR",
        };
        write!(f, "{}", action_str)
    }
}

impl FromStr for BookAction {
    type Err = anyhow::Error;
    
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "ADD" | "A" | "0" => Ok(Self::Add),
            "UPDATE" | "U" | "1" => Ok(Self::Update),
            "DELETE" | "D" | "2" => Ok(Self::Delete),
            "CLEAR" | "C" | "3" => Ok(Self::Clear),
            _ => Err(anyhow::anyhow!("Unknown book action: {}", s)),
        }
    }
}

/// Order side enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderSide {
    /// Buy order
    Buy,
    /// Sell order
    Sell,
}

impl Display for OrderSide {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let side_str = match self {
            Self::Buy => "BUY",
            Self::Sell => "SELL",
        };
        write!(f, "{}", side_str)
    }
}

impl FromStr for OrderSide {
    type Err = anyhow::Error;
    
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "BUY" | "B" | "1" => Ok(Self::Buy),
            "SELL" | "S" | "2" => Ok(Self::Sell),
            _ => Err(anyhow::anyhow!("Unknown order side: {}", s)),
        }
    }
}

/// Security type enumeration from 4OTC
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SecurityType {
    /// Currency pair (FX spot)
    CurrencyPair,
    /// Crypto currency pair
    CryptoCurrencyPair,
    /// Futures contract
    Future,
    /// Option contract
    Option,
    /// Swap contract
    Swap,
    /// Unknown security type
    Unknown,
}

impl Display for SecurityType {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let type_str = match self {
            Self::CurrencyPair => "CURRENCY_PAIR",
            Self::CryptoCurrencyPair => "CRYPTO_CURRENCY_PAIR",
            Self::Future => "FUTURE",
            Self::Option => "OPTION",
            Self::Swap => "SWAP",
            Self::Unknown => "UNKNOWN",
        };
        write!(f, "{}", type_str)
    }
}

impl FromStr for SecurityType {
    type Err = anyhow::Error;
    
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "CURRENCY_PAIR" | "CURRENCYPAIR" | "FX" | "SPOT" => Ok(Self::CurrencyPair),
            "CRYPTO_CURRENCY_PAIR" | "CRYPTOCURRENCYPAIR" | "CRYPTO" => Ok(Self::CryptoCurrencyPair),
            "FUTURE" | "FUTURES" | "FUT" => Ok(Self::Future),
            "OPTION" | "OPTIONS" | "OPT" => Ok(Self::Option),
            "SWAP" | "SWAPS" => Ok(Self::Swap),
            "UNKNOWN" => Ok(Self::Unknown),
            _ => Err(anyhow::anyhow!("Unknown security type: {}", s)),
        }
    }
}

/// Request type for market data subscriptions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum RequestType {
    /// Subscribe to market data
    Subscribe,
    /// Unsubscribe from market data
    Unsubscribe,
    /// Request snapshot
    Snapshot,
}

impl Display for RequestType {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let type_str = match self {
            Self::Subscribe => "SUBSCRIBE",
            Self::Unsubscribe => "UNSUBSCRIBE",
            Self::Snapshot => "SNAPSHOT",
        };
        write!(f, "{}", type_str)
    }
}

impl FromStr for RequestType {
    type Err = anyhow::Error;
    
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "SUBSCRIBE" | "SUB" | "1" => Ok(Self::Subscribe),
            "UNSUBSCRIBE" | "UNSUB" | "2" => Ok(Self::Unsubscribe),
            "SNAPSHOT" | "SNAP" | "0" => Ok(Self::Snapshot),
            _ => Err(anyhow::anyhow!("Unknown request type: {}", s)),
        }
    }
}

/// Error types specific to 4OTC adapter
#[derive(Debug, thiserror::Error)]
pub enum FourOtcError {
    /// Connection error
    #[error("Connection error: {0}")]
    Connection(String),
    
    /// NATS subscription error
    #[error("NATS subscription error: {0}")]
    Subscription(String),
    
    /// Message parsing error
    #[error("Message parsing error: {0}")]
    MessageParsing(String),
    
    /// Data conversion error
    #[error("Data conversion error: {0}")]
    DataConversion(String),
    
    /// Configuration error
    #[error("Configuration error: {0}")]
    Configuration(String),
    
    /// Authentication error
    #[error("Authentication error: {0}")]
    Authentication(String),
    
    /// Rate limit exceeded
    #[error("Rate limit exceeded: {0}")]
    RateLimit(String),
    
    /// Unknown error
    #[error("Unknown error: {0}")]
    Unknown(String),
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_connection_state_display() {
        assert_eq!(ConnectionState::Connected.to_string(), "CONNECTED");
        assert_eq!(ConnectionState::Disconnected.to_string(), "DISCONNECTED");
        assert_eq!(ConnectionState::Connecting.to_string(), "CONNECTING");
    }
    
    #[test]
    fn test_message_type_conversion() {
        assert_eq!(MessageType::from_str("HEARTBEAT").unwrap(), MessageType::Heartbeat);
        assert_eq!(MessageType::from_str("TRADE").unwrap(), MessageType::Trade);
        assert_eq!(
            MessageType::from_str("ORDER_BOOK_SNAPSHOT").unwrap(),
            MessageType::OrderBookSnapshot
        );
        assert!(MessageType::from_str("INVALID").is_err());
    }
    
    #[test]
    fn test_book_action_conversion() {
        assert_eq!(BookAction::from_str("ADD").unwrap(), BookAction::Add);
        assert_eq!(BookAction::from_str("A").unwrap(), BookAction::Add);
        assert_eq!(BookAction::from_str("0").unwrap(), BookAction::Add);
        assert_eq!(BookAction::from_str("DELETE").unwrap(), BookAction::Delete);
        assert!(BookAction::from_str("INVALID").is_err());
    }
    
    #[test]
    fn test_order_side_conversion() {
        assert_eq!(OrderSide::from_str("BUY").unwrap(), OrderSide::Buy);
        assert_eq!(OrderSide::from_str("B").unwrap(), OrderSide::Buy);
        assert_eq!(OrderSide::from_str("1").unwrap(), OrderSide::Buy);
        assert_eq!(OrderSide::from_str("SELL").unwrap(), OrderSide::Sell);
        assert!(OrderSide::from_str("INVALID").is_err());
    }
    
    #[test]
    fn test_security_type_conversion() {
        assert_eq!(SecurityType::from_str("CURRENCY_PAIR").unwrap(), SecurityType::CurrencyPair);
        assert_eq!(SecurityType::from_str("FX").unwrap(), SecurityType::CurrencyPair);
        assert_eq!(SecurityType::from_str("CRYPTO").unwrap(), SecurityType::CryptoCurrencyPair);
        assert_eq!(SecurityType::from_str("FUTURE").unwrap(), SecurityType::Future);
        assert!(SecurityType::from_str("INVALID").is_err());
    }
    
    #[test]
    fn test_request_type_conversion() {
        assert_eq!(RequestType::from_str("SUBSCRIBE").unwrap(), RequestType::Subscribe);
        assert_eq!(RequestType::from_str("SUB").unwrap(), RequestType::Subscribe);
        assert_eq!(RequestType::from_str("1").unwrap(), RequestType::Subscribe);
        assert_eq!(RequestType::from_str("SNAPSHOT").unwrap(), RequestType::Snapshot);
        assert!(RequestType::from_str("INVALID").is_err());
    }
}