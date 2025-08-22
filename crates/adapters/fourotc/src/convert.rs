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

//! Data conversion utilities for transforming 4OTC messages to Nautilus data types.

use std::collections::HashMap;

use anyhow::{anyhow, Result};
use nautilus_core::{time::get_atomic_clock_realtime, UnixNanos};
use nautilus_model::{
    data::{
        delta::OrderBookDelta, depth::OrderBookDepth10, order::BookOrder, quote::QuoteTick,
        trade::TradeTick, Data,
    },
    enums::{AggressorSide as NautilusAggressorSide, BookAction, OrderSide},
    identifiers::{InstrumentId, TradeId, Venue},
    types::{Price, Quantity},
};

use crate::{
    enums::{BookAction as FourOtcBookAction, MessageType, OrderSide as FourOtcOrderSide},
    proto::{self, MarketDataMessage},
    types::FourOtcSymbol,
};

/// Converts 4OTC decoded messages to Nautilus data types
pub struct DataConverter {
    venue: Venue,
    instrument_map: HashMap<u32, InstrumentId>,
    symbol_map: HashMap<u32, FourOtcSymbol>,
}

impl DataConverter {
    /// Creates a new data converter
    pub fn new(venue: Venue) -> Self {
        Self {
            venue,
            instrument_map: HashMap::new(),
            symbol_map: HashMap::new(),
        }
    }

    /// Registers an instrument mapping for security ID to InstrumentId
    pub fn register_instrument(&mut self, security_id: u32, instrument_id: InstrumentId) {
        self.instrument_map.insert(security_id, instrument_id);
    }

    /// Registers a symbol mapping for security ID to FourOtcSymbol
    pub fn register_symbol(&mut self, security_id: u32, symbol: FourOtcSymbol) {
        self.symbol_map.insert(security_id, symbol);
    }

    /// Gets instrument ID for a security ID
    fn get_instrument_id(&self, security_id: i32) -> Result<InstrumentId> {
        self.instrument_map
            .get(&(security_id as u32))
            .copied()
            .ok_or_else(|| anyhow!("Unknown security ID: {}", security_id))
    }

    /// Converts a 4OTC protobuf message to Nautilus data
    pub fn convert_message(&self, message: &MarketDataMessage) -> Result<Option<Data>> {
        let ts_init = UnixNanos::from(get_atomic_clock_realtime().get_time_ns());

        match &message.message_type {
            Some(proto::market_data_message::MessageType::OrderBookSnapshot(snapshot)) => {
                self.convert_order_book_snapshot(snapshot, ts_init)
            }
            Some(proto::market_data_message::MessageType::OrderBookUpdate(update)) => {
                // For now, treat updates as snapshots
                // TODO: Implement proper delta handling
                if let Some(book) = &update.book {
                    self.convert_order_book_snapshot(book, ts_init)
                } else {
                    Ok(None)
                }
            }
            Some(proto::market_data_message::MessageType::Trade(trade)) => {
                self.convert_trade(trade, ts_init)
            }
            Some(proto::market_data_message::MessageType::Heartbeat(_)) |
            Some(proto::market_data_message::MessageType::UnsequencedHeartbeat(_)) => {
                // Heartbeats don't produce market data
                Ok(None)
            }
            Some(proto::market_data_message::MessageType::SecurityDefinition(_)) => {
                // Security definitions are handled during instrument setup
                Ok(None)
            }
            Some(proto::market_data_message::MessageType::SecurityStatus(_)) => {
                // Security status updates could be converted to instrument status
                // TODO: Implement if needed
                Ok(None)
            }
            _ => {
                // Other message types are not converted to market data
                Ok(None)
            }
        }
    }

    /// Converts an order book snapshot to Nautilus OrderBookDepth10
    fn convert_order_book_snapshot(
        &self,
        book: &proto::OrderBookSnapshot,
        ts_init: UnixNanos,
    ) -> Result<Option<Data>> {
        let instrument_id = self.get_instrument_id(book.security_id)?;

        // Convert bids (highest prices first)
        let mut bids = Vec::new();
        for (i, entry) in book.bids.iter().take(10).enumerate() {
            let order = BookOrder::new(
                OrderSide::Buy,
                Price::from_raw((entry.price as i64).into(), 8),
                Quantity::from_raw((entry.quantity as u64).into(), 8),
                i as u64,
            );
            bids.push(order);
        }

        // Convert asks (lowest prices first)
        let mut asks = Vec::new();
        for (i, entry) in book.asks.iter().take(10).enumerate() {
            let order = BookOrder::new(
                OrderSide::Sell,
                Price::from_raw((entry.price as i64).into(), 8),
                Quantity::from_raw((entry.quantity as u64).into(), 8),
                i as u64,
            );
            asks.push(order);
        }

        // Pad with empty orders if needed
        while bids.len() < 10 {
            bids.push(BookOrder::new(
                OrderSide::Buy,
                Price::from("0"),
                Quantity::from("0"),
                bids.len() as u64,
            ));
        }
        while asks.len() < 10 {
            asks.push(BookOrder::new(
                OrderSide::Sell,
                Price::from("0"),
                Quantity::from("0"),
                asks.len() as u64,
            ));
        }

        let depth = OrderBookDepth10::new(
            instrument_id,
            [
                bids[0], bids[1], bids[2], bids[3], bids[4], bids[5], bids[6], bids[7], bids[8],
                bids[9],
            ],
            [
                asks[0], asks[1], asks[2], asks[3], asks[4], asks[5], asks[6], asks[7], asks[8],
                asks[9],
            ],
            [1; 10], // bid_counts
            [1; 10], // ask_counts
            0, // flags
            0, // sequence
            UnixNanos::from(book.timestamp as u64),
            ts_init,
        );

        Ok(Some(Data::Depth10(Box::new(depth))))
    }

    /// Converts a 4OTC trade to Nautilus TradeTick
    fn convert_trade(
        &self,
        trade: &proto::Trade,
        ts_init: UnixNanos,
    ) -> Result<Option<Data>> {
        let instrument_id = self.get_instrument_id(trade.security_id)?;

        let aggressor_side = match proto::AggressorSide::try_from(trade.aggressor_side) {
            Ok(proto::AggressorSide::AggressorBuy) => NautilusAggressorSide::Buyer,
            Ok(proto::AggressorSide::AggressorSell) => NautilusAggressorSide::Seller,
            _ => NautilusAggressorSide::NoAggressor,
        };

        let trade_tick = TradeTick::new(
            instrument_id,
            Price::from_raw((trade.price as i64).into(), 8),
            Quantity::from_raw((trade.quantity as u64).into(), 8),
            aggressor_side,
            TradeId::from(&trade.trade_id),
            UnixNanos::from(trade.timestamp as u64),
            ts_init,
        );

        Ok(Some(Data::Trade(trade_tick)))
    }

    /// Converts a 4OTC price level to Nautilus BookOrder
    fn convert_book_order(
        &self,
        entry: &proto::OrderBookLevel,
        side: OrderSide,
        order_id: Option<u64>,
    ) -> BookOrder {
        BookOrder::new(
            side,
            Price::from_raw((entry.price as i64).into(), 8),
            Quantity::from_raw((entry.quantity as u64).into(), 8),
            order_id.unwrap_or(0),
        )
    }

    /// Converts order book deltas to Nautilus OrderBookDelta
    pub fn convert_order_book_delta(
        &self,
        security_id: u32,
        action: FourOtcBookAction,
        side: FourOtcOrderSide,
        price: f64,
        quantity: f64,
        order_id: Option<u64>,
        ts_event: u64,
    ) -> Result<OrderBookDelta> {
        let instrument_id = self.get_instrument_id(security_id.try_into().unwrap())?;
        let ts_init = UnixNanos::from(get_atomic_clock_realtime().get_time_ns());

        let nautilus_action = match action {
            FourOtcBookAction::Add => BookAction::Add,
            FourOtcBookAction::Update => BookAction::Update,
            FourOtcBookAction::Delete => BookAction::Delete,
            FourOtcBookAction::Clear => BookAction::Clear,
        };

        let nautilus_side = match side {
            FourOtcOrderSide::Buy => OrderSide::Buy,
            FourOtcOrderSide::Sell => OrderSide::Sell,
        };

        let order = BookOrder::new(
            nautilus_side,
            Price::from_raw((price as i64).into(), 8),
            Quantity::from_raw((quantity as u64).into(), 8),
            order_id.unwrap_or(0),
        );

        Ok(OrderBookDelta::new(
            instrument_id,
            nautilus_action,
            order,
            0, // flags
            0, // sequence
            UnixNanos::from(ts_event),
            ts_init,
        ))
    }

    /// Extracts message type from MarketDataMessage
    pub fn get_message_type(message: &MarketDataMessage) -> MessageType {
        match &message.message_type {
            Some(proto::market_data_message::MessageType::Heartbeat(_)) => MessageType::Heartbeat,
            Some(proto::market_data_message::MessageType::UnsequencedHeartbeat(_)) => MessageType::UnsequencedHeartbeat,
            Some(proto::market_data_message::MessageType::RequestReject(_)) => MessageType::RequestReject,
            Some(proto::market_data_message::MessageType::RequestAccept(_)) => MessageType::RequestAccept,
            Some(proto::market_data_message::MessageType::OrderBookSnapshot(_)) => MessageType::OrderBookSnapshot,
            Some(proto::market_data_message::MessageType::OrderBookUpdate(_)) => MessageType::OrderBookUpdate,
            Some(proto::market_data_message::MessageType::Trade(_)) => MessageType::Trade,
            Some(proto::market_data_message::MessageType::SecurityDefinition(_)) => MessageType::SecurityDefinition,
            Some(proto::market_data_message::MessageType::SecurityDefinitionExtension(_)) => {
                MessageType::SecurityDefinitionExtension
            }
            Some(proto::market_data_message::MessageType::SecurityStatus(_)) => MessageType::SecurityStatus,
            Some(proto::market_data_message::MessageType::SnapshotRequest(_)) => MessageType::SnapshotRequest,
            Some(proto::market_data_message::MessageType::TradesRequest(_)) => MessageType::TradesRequest,
            Some(proto::market_data_message::MessageType::SecurityDefinitionRequest(_)) => MessageType::SecurityDefinitionRequest,
            Some(proto::market_data_message::MessageType::ClientDisconnectRequest(_)) => MessageType::ClientDisconnectRequest,
            Some(proto::market_data_message::MessageType::UnknownMessage(_)) => MessageType::Unknown,
            None => MessageType::Unknown,
        }
    }

    /// Creates a QuoteTick from order book snapshot
    pub fn create_quote_from_book(
        &self,
        book: &proto::OrderBookSnapshot,
    ) -> Result<QuoteTick> {
        let instrument_id = self.get_instrument_id(book.security_id)?;
        let ts_init = UnixNanos::from(get_atomic_clock_realtime().get_time_ns());

        let best_bid = book
            .bids
            .first()
            .map(|entry| Price::from_raw((entry.price as i64).into(), 8))
            .unwrap_or_else(|| Price::from("0"));

        let best_ask = book
            .asks
            .first()
            .map(|entry| Price::from_raw((entry.price as i64).into(), 8))
            .unwrap_or_else(|| Price::from("0"));

        let bid_size = book
            .bids
            .first()
            .map(|entry| Quantity::from_raw((entry.quantity as u64).into(), 8))
            .unwrap_or_else(|| Quantity::from("0"));

        let ask_size = book
            .asks
            .first()
            .map(|entry| Quantity::from_raw((entry.quantity as u64).into(), 8))
            .unwrap_or_else(|| Quantity::from("0"));

        Ok(QuoteTick::new(
            instrument_id,
            best_bid,
            best_ask,
            bid_size,
            ask_size,
            UnixNanos::from(book.timestamp as u64),
            ts_init,
        ))
    }

    /// Validates and normalizes a price value
    pub fn normalize_price(raw_price: f64, precision: u8) -> Result<Price> {
        if raw_price.is_finite() && raw_price >= 0.0 {
            Ok(Price::from_raw(((raw_price * 10f64.powi(precision as i32)) as i64).into(), precision))
        } else {
            Err(anyhow!("Invalid price value: {}", raw_price))
        }
    }

    /// Validates and normalizes a quantity value
    pub fn normalize_quantity(raw_quantity: f64, precision: u8) -> Result<Quantity> {
        if raw_quantity.is_finite() && raw_quantity >= 0.0 {
            Ok(Quantity::from_raw(
                ((raw_quantity * 10f64.powi(precision as i32)) as u64).into(),
                precision,
            ))
        } else {
            Err(anyhow!("Invalid quantity value: {}", raw_quantity))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nautilus_model::identifiers::Symbol;

    #[test]
    fn test_data_converter_creation() {
        let venue = Venue::from("4OTC");
        let converter = DataConverter::new(venue);
        assert_eq!(converter.venue, venue);
        assert!(converter.instrument_map.is_empty());
        assert!(converter.symbol_map.is_empty());
    }

    #[test]
    fn test_instrument_registration() {
        let venue = Venue::from("4OTC");
        let mut converter = DataConverter::new(venue);
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");

        converter.register_instrument(100, instrument_id);
        assert_eq!(converter.get_instrument_id(100).unwrap(), instrument_id);
        assert!(converter.get_instrument_id(999).is_err());
    }

    #[test]
    fn test_normalize_price() {
        let price = DataConverter::normalize_price(123.456, 2).unwrap();
        assert_eq!(price.raw, 12346); // 123.46 * 100

        let price = DataConverter::normalize_price(0.0001, 8).unwrap();
        assert_eq!(price.raw, 10000); // 0.0001 * 10^8

        assert!(DataConverter::normalize_price(f64::NAN, 2).is_err());
        assert!(DataConverter::normalize_price(-1.0, 2).is_err());
    }

    #[test]
    fn test_normalize_quantity() {
        let quantity = DataConverter::normalize_quantity(123.456, 3).unwrap();
        assert_eq!(quantity.raw, 123456); // 123.456 * 1000

        let quantity = DataConverter::normalize_quantity(0.0001, 8).unwrap();
        assert_eq!(quantity.raw, 10000); // 0.0001 * 10^8

        assert!(DataConverter::normalize_quantity(f64::NAN, 3).is_err());
        assert!(DataConverter::normalize_quantity(-1.0, 3).is_err());
    }

    #[test]
    fn test_message_type_extraction() {
        use crate::proto;
        
        let heartbeat_msg = MarketDataMessage {
            message_type: Some(proto::market_data_message::MessageType::Heartbeat(proto::Heartbeat {})),
            timestamp_nanos: 0,
            message_id: String::new(),
        };
        assert_eq!(DataConverter::get_message_type(&heartbeat_msg), MessageType::Heartbeat);

        let request_reject_msg = MarketDataMessage {
            message_type: Some(proto::market_data_message::MessageType::RequestReject(proto::RequestReject {
                request_id: "123".to_string(),
                reason: "Invalid".to_string(),
            })),
            timestamp_nanos: 0,
            message_id: String::new(),
        };
        assert_eq!(
            DataConverter::get_message_type(&request_reject_msg),
            MessageType::RequestReject
        );
    }
}