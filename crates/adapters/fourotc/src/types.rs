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

//! Type definitions for the 4OTC adapter.

use std::{
    fmt::{Display, Formatter},
    str::FromStr,
};

use nautilus_model::{
    identifiers::Symbol,
    instruments::CurrencyPair,
    types::{Price, Quantity},
};
use serde::{Deserialize, Serialize};

/// 4OTC-specific symbol type that wraps Nautilus Symbol
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct FourOtcSymbol {
    inner: Symbol,
    security_id: u32,
    venue_id: u32,
}

impl FourOtcSymbol {
    /// Creates a new 4OTC symbol
    pub fn new(symbol: Symbol, security_id: u32, venue_id: u32) -> Self {
        Self {
            inner: symbol,
            security_id,
            venue_id,
        }
    }
    
    /// Returns the underlying Nautilus symbol
    pub fn inner(&self) -> &Symbol {
        &self.inner
    }
    
    /// Returns the 4OTC security ID
    pub fn security_id(&self) -> u32 {
        self.security_id
    }
    
    /// Returns the 4OTC venue ID
    pub fn venue_id(&self) -> u32 {
        self.venue_id
    }
    
    /// Creates a symbol from 4OTC identifiers
    pub fn from_ids(security_id: u32, venue_id: u32, symbol_str: &str) -> anyhow::Result<Self> {
        let symbol = Symbol::new(symbol_str);
        Ok(Self::new(symbol, security_id, venue_id))
    }
}

impl Display for FourOtcSymbol {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}:{}:{}", self.inner, self.security_id, self.venue_id)
    }
}

impl From<FourOtcSymbol> for Symbol {
    fn from(symbol: FourOtcSymbol) -> Self {
        symbol.inner
    }
}

/// 4OTC instrument type that extends Nautilus instrument definitions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FourOtcInstrument {
    /// The underlying Nautilus instrument
    pub instrument: CurrencyPair,
    
    /// 4OTC-specific security ID
    pub security_id: u32,
    
    /// 4OTC-specific venue ID
    pub venue_id: u32,
    
    /// Trading status on 4OTC
    pub trading_status: TradingStatus,
    
    /// Minimum order size
    pub min_quantity: Quantity,
    
    /// Maximum order size
    pub max_quantity: Quantity,
    
    /// Tick size for price movements
    pub tick_size: Price,
    
    /// Lot size multiplier
    pub lot_size: Quantity,
    
    /// Display factor for price formatting
    pub display_factor: Option<f64>,
    
    /// Additional attributes specific to 4OTC
    pub attributes: std::collections::HashMap<String, String>,
}

impl FourOtcInstrument {
    /// Creates a new 4OTC instrument
    pub fn new(
        instrument: CurrencyPair,
        security_id: u32,
        venue_id: u32,
        tick_size: Price,
        lot_size: Quantity,
    ) -> Self {
        Self {
            instrument,
            security_id,
            venue_id,
            trading_status: TradingStatus::Trading,
            min_quantity: Quantity::from("0.0001"),
            max_quantity: Quantity::from("1000000.0"),
            tick_size,
            lot_size,
            display_factor: None,
            attributes: std::collections::HashMap::new(),
        }
    }
    
    /// Returns the 4OTC symbol for this instrument
    pub fn fourotc_symbol(&self) -> FourOtcSymbol {
        FourOtcSymbol::new(
            self.instrument.id.symbol,
            self.security_id,
            self.venue_id,
        )
    }
    
    /// Updates the trading status
    pub fn set_trading_status(&mut self, status: TradingStatus) {
        self.trading_status = status;
    }
    
    /// Adds or updates an attribute
    pub fn set_attribute(&mut self, key: String, value: String) {
        self.attributes.insert(key, value);
    }
    
    /// Gets an attribute value
    pub fn get_attribute(&self, key: &str) -> Option<&String> {
        self.attributes.get(key)
    }
    
    /// Checks if the instrument is actively trading
    pub fn is_trading(&self) -> bool {
        matches!(self.trading_status, TradingStatus::Trading)
    }
}

/// Trading status enumeration for 4OTC instruments
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum TradingStatus {
    /// Instrument is actively trading
    Trading,
    /// Trading is halted
    Halted,
    /// Trading is suspended
    Suspended,
    /// Pre-trading state
    PreTrading,
    /// Post-trading state
    PostTrading,
    /// Auction mode
    Auction,
    /// Instrument is not available for trading
    NotAvailable,
}

impl Display for TradingStatus {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let status_str = match self {
            Self::Trading => "TRADING",
            Self::Halted => "HALTED",
            Self::Suspended => "SUSPENDED",
            Self::PreTrading => "PRE_TRADING",
            Self::PostTrading => "POST_TRADING",
            Self::Auction => "AUCTION",
            Self::NotAvailable => "NOT_AVAILABLE",
        };
        write!(f, "{}", status_str)
    }
}

impl FromStr for TradingStatus {
    type Err = anyhow::Error;
    
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "TRADING" | "1" => Ok(Self::Trading),
            "HALTED" | "2" => Ok(Self::Halted),
            "SUSPENDED" | "3" => Ok(Self::Suspended),
            "PRE_TRADING" | "4" => Ok(Self::PreTrading),
            "POST_TRADING" | "5" => Ok(Self::PostTrading),
            "AUCTION" | "6" => Ok(Self::Auction),
            "NOT_AVAILABLE" | "0" => Ok(Self::NotAvailable),
            _ => Err(anyhow::anyhow!("Unknown trading status: {}", s)),
        }
    }
}

/// Order book entry from 4OTC
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FourOtcBookEntry {
    /// Price level
    pub price: Price,
    /// Quantity at this price level
    pub quantity: Quantity,
    /// Number of orders at this level (if available)
    pub order_count: Option<u32>,
    /// Venue-specific order ID (if available)
    pub order_id: Option<String>,
}

impl FourOtcBookEntry {
    /// Creates a new book entry
    pub fn new(price: Price, quantity: Quantity) -> Self {
        Self {
            price,
            quantity,
            order_count: None,
            order_id: None,
        }
    }
    
    /// Creates a book entry with order count
    pub fn with_order_count(price: Price, quantity: Quantity, order_count: u32) -> Self {
        Self {
            price,
            quantity,
            order_count: Some(order_count),
            order_id: None,
        }
    }
}

/// 4OTC trade information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FourOtcTrade {
    /// Trade ID from 4OTC
    pub trade_id: String,
    /// Trade price
    pub price: Price,
    /// Trade quantity
    pub quantity: Quantity,
    /// Side of the aggressor
    pub aggressor_side: AggressorSide,
    /// Trade timestamp (UNIX nanoseconds)
    pub timestamp: u64,
    /// Trade conditions/flags
    pub conditions: Vec<String>,
}

/// Aggressor side enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AggressorSide {
    /// Buy side was the aggressor
    Buy,
    /// Sell side was the aggressor
    Sell,
    /// Unknown or no aggressor
    Unknown,
}

impl Display for AggressorSide {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        let side_str = match self {
            Self::Buy => "BUY",
            Self::Sell => "SELL",
            Self::Unknown => "UNKNOWN",
        };
        write!(f, "{}", side_str)
    }
}

impl FromStr for AggressorSide {
    type Err = anyhow::Error;
    
    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_uppercase().as_str() {
            "BUY" | "B" | "1" => Ok(Self::Buy),
            "SELL" | "S" | "2" => Ok(Self::Sell),
            "UNKNOWN" | "U" | "0" => Ok(Self::Unknown),
            _ => Err(anyhow::anyhow!("Unknown aggressor side: {}", s)),
        }
    }
}

/// Statistics for the data client
#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct ClientStats {
    /// Total messages received
    pub messages_received: u64,
    /// Messages processed successfully
    pub messages_processed: u64,
    /// Messages that failed processing
    pub processing_errors: u64,
    /// NATS connection errors
    pub connection_errors: u64,
    /// Last message timestamp
    pub last_message_time: Option<u64>,
    /// Connection uptime in seconds
    pub uptime_secs: u64,
}

impl ClientStats {
    /// Increments message received counter
    pub fn increment_received(&mut self) {
        self.messages_received += 1;
    }
    
    /// Increments message processed counter
    pub fn increment_processed(&mut self) {
        self.messages_processed += 1;
    }
    
    /// Increments processing error counter
    pub fn increment_processing_error(&mut self) {
        self.processing_errors += 1;
    }
    
    /// Increments connection error counter
    pub fn increment_connection_error(&mut self) {
        self.connection_errors += 1;
    }
    
    /// Updates last message time
    pub fn update_last_message_time(&mut self, timestamp: u64) {
        self.last_message_time = Some(timestamp);
    }
    
    /// Updates uptime
    pub fn update_uptime(&mut self, uptime_secs: u64) {
        self.uptime_secs = uptime_secs;
    }
    
    /// Calculates processing success rate
    pub fn success_rate(&self) -> f64 {
        if self.messages_received == 0 {
            0.0
        } else {
            self.messages_processed as f64 / self.messages_received as f64
        }
    }
    
    /// Calculates error rate
    pub fn error_rate(&self) -> f64 {
        if self.messages_received == 0 {
            0.0
        } else {
            self.processing_errors as f64 / self.messages_received as f64
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nautilus_model::{
        identifiers::{InstrumentId, Venue},
        types::Currency,
    };
    
    #[test]
    fn test_fourotc_symbol_creation() {
        let symbol = Symbol::from("BTCUSD");
        let fourotc_symbol = FourOtcSymbol::new(symbol, 100, 1);
        
        assert_eq!(fourotc_symbol.security_id(), 100);
        assert_eq!(fourotc_symbol.venue_id(), 1);
        assert_eq!(fourotc_symbol.inner(), &symbol);
    }
    
    #[test]
    fn test_fourotc_symbol_display() {
        let symbol = Symbol::from("BTCUSD");
        let fourotc_symbol = FourOtcSymbol::new(symbol, 100, 1);
        
        assert_eq!(fourotc_symbol.to_string(), "BTCUSD:100:1");
    }
    
    #[test]
    fn test_trading_status_conversion() {
        assert_eq!(TradingStatus::from_str("TRADING").unwrap(), TradingStatus::Trading);
        assert_eq!(TradingStatus::from_str("1").unwrap(), TradingStatus::Trading);
        assert_eq!(TradingStatus::from_str("HALTED").unwrap(), TradingStatus::Halted);
        assert_eq!(TradingStatus::from_str("2").unwrap(), TradingStatus::Halted);
        
        assert!(TradingStatus::from_str("INVALID").is_err());
    }
    
    #[test]
    fn test_aggressor_side_conversion() {
        assert_eq!(AggressorSide::from_str("BUY").unwrap(), AggressorSide::Buy);
        assert_eq!(AggressorSide::from_str("B").unwrap(), AggressorSide::Buy);
        assert_eq!(AggressorSide::from_str("1").unwrap(), AggressorSide::Buy);
        assert_eq!(AggressorSide::from_str("SELL").unwrap(), AggressorSide::Sell);
        assert_eq!(AggressorSide::from_str("S").unwrap(), AggressorSide::Sell);
        assert_eq!(AggressorSide::from_str("2").unwrap(), AggressorSide::Sell);
        
        assert!(AggressorSide::from_str("INVALID").is_err());
    }
    
    #[test]
    fn test_client_stats() {
        let mut stats = ClientStats::default();
        
        stats.increment_received();
        stats.increment_processed();
        stats.increment_received();
        stats.increment_processing_error();
        
        assert_eq!(stats.messages_received, 2);
        assert_eq!(stats.messages_processed, 1);
        assert_eq!(stats.processing_errors, 1);
        assert_eq!(stats.success_rate(), 0.5);
        assert_eq!(stats.error_rate(), 0.5);
    }
    
    #[test]
    fn test_fourotc_instrument_creation() {
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        let instrument = CurrencyPair::new(
            instrument_id,
            Symbol::from("BTCUSD"),
            Currency::USD,
            Currency::BTC,
            None,
            None,
            Price::from("0.01"),
            Quantity::from("0.0001"),
            None,
            None,
            None,
            None,
            0,
        );
        
        let fourotc_instrument = FourOtcInstrument::new(
            instrument,
            100,
            1,
            Price::from("0.01"),
            Quantity::from("0.0001"),
        );
        
        assert_eq!(fourotc_instrument.security_id, 100);
        assert_eq!(fourotc_instrument.venue_id, 1);
        assert!(fourotc_instrument.is_trading());
    }
}