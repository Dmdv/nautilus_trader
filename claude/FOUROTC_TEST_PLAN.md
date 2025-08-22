# Comprehensive Test Plan for 4OTC Adapter

## Overview

This document outlines a comprehensive testing strategy for the 4OTC market data adapter for Nautilus Trader. The adapter consumes **protobuf-encoded messages from NATS** and converts them to Nautilus data types. The test plan covers unit tests, integration tests, performance benchmarks, and production readiness validation.

## Architecture

The 4OTC adapter operates in this data flow:
```
4OTC WebSocket → 4OTC Adapter → SBE Decoder → Protobuf Encoder → NATS → Nautilus 4OTC Adapter → Protobuf Decoder → Nautilus Types
```

**Key Points:**
- Messages received from NATS are **already decoded from SBE** by the 4OTC adapter
- Messages are **protobuf-encoded** using the `marketdata.proto` schema
- No SBE decoding is performed in the Nautilus adapter
- Direct protobuf → Nautilus type conversion

## Testing Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Unit Tests    │    │ Integration  │    │  Performance    │
│                 │    │    Tests     │    │   Benchmarks    │
│ - Components    │    │              │    │                 │
│ - Conversions   │    │ - NATS E2E   │    │ - Throughput    │
│ - Validation    │    │ - Message    │    │ - Latency       │
│                 │    │   Pipeline   │    │ - Memory Usage  │
└─────────────────┘    └──────────────┘    └─────────────────┘
         │                       │                    │
         └───────────────────────┼────────────────────┘
                                 │
         ┌─────────────────────────────────────────┐
         │          Production Tests               │
         │                                         │
         │ - Load Testing                          │
         │ - Failover Scenarios                    │
         │ - Long-Running Stability                │
         │ - Security Validation                   │
         └─────────────────────────────────────────┘
```

## Test Categories

### 1. Unit Tests

#### 1.1 Configuration Module Tests

**File**: `tests/unit/config_tests.rs`

```rust
#[cfg(test)]
mod config_tests {
    use super::*;
    use fourotc::config::*;
    
    #[test]
    fn test_development_config_creation() {
        let config = FourOtcDataClientConfig::development();
        assert_eq!(config.debug_mode, true);
        assert_eq!(config.buffer_size, 10000);
        assert_eq!(config.heartbeat_interval_secs, 10);
    }
    
    #[test]
    fn test_production_config_creation() {
        let config = FourOtcDataClientConfig::production();
        assert_eq!(config.debug_mode, false);
        assert_eq!(config.buffer_size, 100000);
        assert_eq!(config.heartbeat_interval_secs, 30);
    }
    
    #[test]
    fn test_nats_config_validation() {
        let mut config = NatsConfig::default();
        config.servers.clear();
        
        let result = config.validate();
        assert!(result.is_err());
        assert!(result.unwrap_err().to_string().contains("No NATS servers configured"));
    }
    
    #[test]
    fn test_config_serialization() {
        let config = FourOtcDataClientConfig::development();
        let json = serde_json::to_string(&config).unwrap();
        let deserialized: FourOtcDataClientConfig = serde_json::from_str(&json).unwrap();
        
        assert_eq!(config.client_id, deserialized.client_id);
        assert_eq!(config.venue, deserialized.venue);
    }
}
```

#### 1.2 Data Conversion Tests

**File**: `tests/unit/convert_tests.rs`

```rust
#[cfg(test)]
mod convert_tests {
    use super::*;
    use fourotc::convert::*;
    use four_otc_markets_market_data::types::market_data::*;
    
    #[test]
    fn test_price_normalization() {
        let result = DataConverter::normalize_price(123.456, 2).unwrap();
        assert_eq!(result.raw, 12346); // 123.46 * 100
        
        let result = DataConverter::normalize_price(0.0001, 8).unwrap();
        assert_eq!(result.raw, 10000); // 0.0001 * 10^8
        
        // Test error cases
        assert!(DataConverter::normalize_price(f64::NAN, 2).is_err());
        assert!(DataConverter::normalize_price(-1.0, 2).is_err());
        assert!(DataConverter::normalize_price(f64::INFINITY, 2).is_err());
    }
    
    #[test]
    fn test_quantity_normalization() {
        let result = DataConverter::normalize_quantity(123.456, 3).unwrap();
        assert_eq!(result.raw, 123456); // 123.456 * 1000
        
        // Test error cases
        assert!(DataConverter::normalize_quantity(f64::NAN, 3).is_err());
        assert!(DataConverter::normalize_quantity(-1.0, 3).is_err());
    }
    
    #[test]
    fn test_order_book_conversion() {
        let venue = Venue::from("4OTC");
        let mut converter = DataConverter::new(venue);
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        converter.register_instrument(100, instrument_id);
        
        // Create test order book snapshot
        let snapshot = proto::OrderBookSnapshot {
            security_id: 100,
            venue_id: 1,
            timestamp: 1234567890000,
            bids: vec![
                proto::OrderBookLevel { price: 50000.0, quantity: 1.5, order_count: 1, min_qty: 0.0, additional_info: vec![] },
                proto::OrderBookLevel { price: 49999.0, quantity: 2.0, order_count: 1, min_qty: 0.0, additional_info: vec![] },
            ],
            asks: vec![
                proto::OrderBookLevel { price: 50001.0, quantity: 1.0, order_count: 1, min_qty: 0.0, additional_info: vec![] },
                proto::OrderBookLevel { price: 50002.0, quantity: 0.5, order_count: 1, min_qty: 0.0, additional_info: vec![] },
            ],
        };
        
        let message = MarketDataMessage {
            message_type: Some(proto::market_data_message::MessageType::OrderBookSnapshot(snapshot)),
            timestamp_nanos: 1234567890000,
            message_id: "test_book".to_string(),
        };
        let result = converter.convert_message(&message).unwrap();
        
        assert!(result.is_some());
        match result.unwrap() {
            Data::Depth10(depth) => {
                assert_eq!(depth.instrument_id, instrument_id);
                assert_eq!(depth.bids.len(), 10);
                assert_eq!(depth.asks.len(), 10);
                
                // Check first bid/ask levels
                assert_eq!(depth.bids[0].price.as_f64(), 50000.0);
                assert_eq!(depth.bids[0].size.as_f64(), 1.5);
                assert_eq!(depth.asks[0].price.as_f64(), 50001.0);
                assert_eq!(depth.asks[0].size.as_f64(), 1.0);
            }
            _ => panic!("Expected Depth10 data"),
        }
    }
    
    #[test]
    fn test_trade_conversion() {
        let venue = Venue::from("4OTC");
        let mut converter = DataConverter::new(venue);
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        converter.register_instrument(100, instrument_id);
        
        let trade = proto::Trade {
            security_id: 100,
            venue_id: 1,
            timestamp: 1234567890000,
            price: 50000.0,
            quantity: 1.5,
            trade_id: "trade123".to_string(),
            aggressor_side: proto::AggressorSide::AggressorBuy as i32,
            conditions: vec![],
            additional_info: vec![],
        };
        
        let message = MarketDataMessage {
            message_type: Some(proto::market_data_message::MessageType::Trade(trade)),
            timestamp_nanos: 1234567890000,
            message_id: "test_trade".to_string(),
        };
        let result = converter.convert_message(&message).unwrap();
        
        assert!(result.is_some());
        match result.unwrap() {
            Data::Trade(trade_tick) => {
                assert_eq!(trade_tick.instrument_id, instrument_id);
                assert_eq!(trade_tick.price.as_f64(), 50000.0);
                assert_eq!(trade_tick.size.as_f64(), 1.5);
                assert_eq!(trade_tick.aggressor_side, NautilusAggressorSide::Buyer);
            }
            _ => panic!("Expected Trade data"),
        }
    }
    
    #[test]
    fn test_message_type_extraction() {
        let heartbeat_msg = MarketDataMessage {
            message_type: Some(proto::market_data_message::MessageType::Heartbeat(proto::Heartbeat {})),
            timestamp_nanos: 0,
            message_id: String::new(),
        };
        assert_eq!(DataConverter::get_message_type(&heartbeat_msg), MessageType::Heartbeat);
        
        let trade_msg = MarketDataMessage {
            message_type: Some(proto::market_data_message::MessageType::Trade(proto::Trade {
                security_id: 100,
                venue_id: 1,
                price: 50000.0,
                quantity: 1.0,
                timestamp: 1234567890000,
                trade_id: "test".to_string(),
                aggressor_side: proto::AggressorSide::AggressorBuy as i32,
                conditions: vec![],
                additional_info: vec![],
            })),
            timestamp_nanos: 0,
            message_id: String::new(),
        };
        assert_eq!(DataConverter::get_message_type(&trade_msg), MessageType::Trade);
    }
}
```

#### 1.3 Type System Tests

**File**: `tests/unit/types_tests.rs`

```rust
#[cfg(test)]
mod types_tests {
    use super::*;
    use fourotc::types::*;
    
    #[test]
    fn test_four_otc_symbol_creation() {
        let symbol = FourOtcSymbol::new(100, 1, "BTCUSD".to_string());
        assert_eq!(symbol.security_id, 100);
        assert_eq!(symbol.venue_id, 1);
        assert_eq!(symbol.symbol, "BTCUSD");
        
        let display = format!("{}", symbol);
        assert_eq!(display, "BTCUSD (100@1)");
    }
    
    #[test]
    fn test_client_stats_calculations() {
        let mut stats = ClientStats::default();
        stats.messages_received = 1000;
        stats.messages_processed = 950;
        stats.processing_errors = 50;
        
        assert_eq!(stats.success_rate(), 0.95);
        assert_eq!(stats.error_rate(), 0.05);
        
        // Test edge cases
        let empty_stats = ClientStats::default();
        assert_eq!(empty_stats.success_rate(), 0.0);
        assert_eq!(empty_stats.error_rate(), 0.0);
    }
    
    #[test]
    fn test_four_otc_instrument_validation() {
        let mut instrument = FourOtcInstrument::default();
        instrument.symbol = FourOtcSymbol::new(100, 1, "BTCUSD".to_string());
        instrument.min_price = Some(0.01);
        instrument.max_price = Some(100000.0);
        instrument.tick_size = Some(0.01);
        instrument.lot_size = Some(0.001);
        
        assert!(instrument.validate().is_ok());
        
        // Test invalid price range
        instrument.min_price = Some(1000.0);
        instrument.max_price = Some(500.0);
        assert!(instrument.validate().is_err());
    }
}
```

#### 1.4 Enumeration Tests

**File**: `tests/unit/enums_tests.rs`

```rust
#[cfg(test)]
mod enums_tests {
    use super::*;
    use fourotc::enums::*;
    
    #[test]
    fn test_connection_state_transitions() {
        let mut state = ConnectionState::Disconnected;
        
        // Valid transitions
        state = ConnectionState::Connecting;
        state = ConnectionState::Connected;
        state = ConnectionState::Reconnecting;
        state = ConnectionState::Connected;
        state = ConnectionState::Disconnecting;
        state = ConnectionState::Disconnected;
        
        // Test display
        assert_eq!(format!("{}", ConnectionState::Connected), "Connected");
        assert_eq!(format!("{}", ConnectionState::Failed), "Failed");
    }
    
    #[test]
    fn test_error_type_categorization() {
        let connection_error = FourOtcError::Connection("NATS server unreachable".to_string());
        let parsing_error = FourOtcError::MessageParsing("Invalid JSON".to_string());
        let conversion_error = FourOtcError::DataConversion("Unknown security ID".to_string());
        
        assert!(matches!(connection_error, FourOtcError::Connection(_)));
        assert!(matches!(parsing_error, FourOtcError::MessageParsing(_)));
        assert!(matches!(conversion_error, FourOtcError::DataConversion(_)));
        
        // Test error display
        assert!(connection_error.to_string().contains("NATS server unreachable"));
    }
    
    #[test]
    fn test_trading_status_states() {
        let states = [
            TradingStatus::PreTrading,
            TradingStatus::Trading,
            TradingStatus::PostTrading,
            TradingStatus::Halted,
            TradingStatus::Suspended,
            TradingStatus::Closed,
        ];
        
        for state in &states {
            // Ensure all states can be displayed
            let _display = format!("{:?}", state);
            
            // Ensure serialization works
            let _json = serde_json::to_string(state).unwrap();
        }
    }
}
```

### 2. Integration Tests

#### 2.1 NATS Integration Tests

**File**: `tests/integration/nats_tests.rs`

```rust
#[cfg(test)]
mod nats_integration_tests {
    use super::*;
    use fourotc::{FourOtcDataClient, config::*};
    use tokio::sync::mpsc;
    use std::time::Duration;
    
    async fn setup_test_nats_server() -> String {
        // Start embedded NATS server for testing
        // Return connection URL
        "nats://localhost:4223".to_string()
    }
    
    #[tokio::test]
    async fn test_nats_connection() {
        let nats_url = setup_test_nats_server().await;
        let mut config = FourOtcDataClientConfig::development();
        config.nats.servers = vec![nats_url];
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        
        // Test connection
        assert!(client.connect().await.is_ok());
        assert_eq!(client.get_connection_state().await, ConnectionState::Connected);
        
        // Test disconnection
        assert!(client.disconnect().await.is_ok());
        assert_eq!(client.get_connection_state().await, ConnectionState::Disconnected);
    }
    
    #[tokio::test]
    async fn test_subscription_management() {
        let nats_url = setup_test_nats_server().await;
        let mut config = FourOtcDataClientConfig::development();
        config.nats.servers = vec![nats_url];
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        
        // Set up data channel
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        // Register instrument and connect
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        // Test trade subscription
        let trade_cmd = SubscribeTrades {
            instrument_id,
            client_id: Some(client.client_id()),
            venue: Some(client.venue().unwrap()),
            command_id: uuid::Uuid::new_v4().into(),
            ts_init: get_atomic_clock_realtime().get_time_ns(),
            params: None,
        };
        
        assert!(client.subscribe_trades(&trade_cmd).is_ok());
        
        // Test order book subscription
        let book_cmd = SubscribeBookDepth10 {
            instrument_id,
            book_type: BookType::L2_MBP,
            client_id: Some(client.client_id()),
            venue: Some(client.venue().unwrap()),
            command_id: uuid::Uuid::new_v4().into(),
            ts_init: get_atomic_clock_realtime().get_time_ns(),
            depth: None,
            managed: false,
            params: None,
        };
        
        assert!(client.subscribe_book_depth10(&book_cmd).is_ok());
        
        // Verify subscriptions are active
        tokio::time::sleep(Duration::from_millis(100)).await;
        // Additional verification logic here
    }
    
    #[tokio::test]
    async fn test_message_processing_pipeline() {
        let nats_url = setup_test_nats_server().await;
        let mut config = FourOtcDataClientConfig::development();
        config.nats.servers = vec![nats_url];
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        // Publish test messages to NATS
        let test_trade = create_test_trade_message(100, 50000.0, 1.5);
        publish_test_message(&client, "market.4otc.trades.1", &test_trade).await;
        
        // Verify message reception and conversion
        let timeout = tokio::time::timeout(Duration::from_secs(1), data_rx.recv()).await;
        assert!(timeout.is_ok());
        
        if let Some(data) = timeout.unwrap() {
            match data {
                Data::Trade(trade_tick) => {
                    assert_eq!(trade_tick.instrument_id, instrument_id);
                    assert_eq!(trade_tick.price.as_f64(), 50000.0);
                    assert_eq!(trade_tick.size.as_f64(), 1.5);
                }
                _ => panic!("Expected Trade data"),
            }
        }
    }
    
    #[tokio::test]
    async fn test_reconnection_logic() {
        let nats_url = setup_test_nats_server().await;
        let mut config = FourOtcDataClientConfig::development();
        config.nats.servers = vec![nats_url.clone()];
        config.nats.max_reconnect_attempts = Some(3);
        config.nats.reconnect_delay_ms = 100;
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        client.connect().await.unwrap();
        
        assert_eq!(client.get_connection_state().await, ConnectionState::Connected);
        
        // Simulate connection loss
        simulate_nats_server_shutdown().await;
        
        // Wait for reconnection attempts
        tokio::time::sleep(Duration::from_millis(500)).await;
        
        // Restart server and verify reconnection
        restart_test_nats_server(&nats_url).await;
        tokio::time::sleep(Duration::from_secs(2)).await;
        
        assert_eq!(client.get_connection_state().await, ConnectionState::Connected);
    }
}
```

#### 2.2 Message Processing Tests

**File**: `tests/integration/message_processing_tests.rs`

```rust
#[cfg(test)]
mod message_processing_tests {
    use super::*;
    use fourotc::*;
    use four_otc_markets_market_data::decoder::*;
    
    #[tokio::test]
    async fn test_end_to_end_trade_processing() {
        let mut client = create_test_client().await;
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        // Create and send test trade message
        let trade_protobuf = create_test_trade_protobuf_message(100, 50000.0, 1.5);
        send_protobuf_message(&client, trade_protobuf).await;
        
        // Verify processed data
        let data = tokio::time::timeout(Duration::from_secs(1), data_rx.recv())
            .await.unwrap().unwrap();
        
        match data {
            Data::Trade(trade_tick) => {
                assert_eq!(trade_tick.instrument_id, instrument_id);
                assert_eq!(trade_tick.price.as_f64(), 50000.0);
                assert_eq!(trade_tick.size.as_f64(), 1.5);
                assert!(trade_tick.ts_event > UnixNanos::default());
                assert!(trade_tick.ts_init > UnixNanos::default());
            }
            _ => panic!("Expected Trade data"),
        }
    }
    
    #[tokio::test]
    async fn test_end_to_end_orderbook_processing() {
        let mut client = create_test_client().await;
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        // Create test order book
        let book_protobuf = create_test_orderbook_protobuf_message(100);
        send_protobuf_message(&client, book_protobuf).await;
        
        let data = tokio::time::timeout(Duration::from_secs(1), data_rx.recv())
            .await.unwrap().unwrap();
        
        match data {
            Data::Depth10(depth) => {
                assert_eq!(depth.instrument_id, instrument_id);
                assert!(depth.bids[0].price > Price::zero());
                assert!(depth.asks[0].price > Price::zero());
                assert!(depth.bids[0].size > Quantity::zero());
                assert!(depth.asks[0].size > Quantity::zero());
            }
            _ => panic!("Expected Depth10 data"),
        }
    }
    
    #[tokio::test]
    async fn test_message_filtering() {
        let mut client = create_test_client().await;
        client.config.enable_message_filtering = true;
        
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        // Register only specific instrument
        let btc_instrument = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, btc_instrument).await;
        
        client.connect().await.unwrap();
        
        // Send messages for different instruments
        send_protobuf_message(&client, create_test_trade_protobuf_message(100, 50000.0, 1.0)).await; // Should be received
        send_protobuf_message(&client, create_test_trade_protobuf_message(200, 3000.0, 2.0)).await;  // Should be filtered
        
        let data = tokio::time::timeout(Duration::from_millis(500), data_rx.recv())
            .await.unwrap().unwrap();
        
        // Should only receive BTC trade
        match data {
            Data::Trade(trade_tick) => {
                assert_eq!(trade_tick.instrument_id, btc_instrument);
                assert_eq!(trade_tick.price.as_f64(), 50000.0);
            }
            _ => panic!("Expected Trade data"),
        }
        
        // Verify no more messages (ETH trade was filtered)
        let timeout_result = tokio::time::timeout(Duration::from_millis(100), data_rx.recv()).await;
        assert!(timeout_result.is_err()); // Should timeout - no more messages
    }
    
    #[tokio::test]
    async fn test_error_handling_and_recovery() {
        let mut client = create_test_client().await;
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        client.connect().await.unwrap();
        
        // Send malformed message
        let malformed_data = vec![0xFF, 0xFF, 0xFF, 0xFF]; // Invalid protobuf
        send_raw_message(&client, malformed_data).await;
        
        // Send valid message after malformed one
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        send_protobuf_message(&client, create_test_trade_protobuf_message(100, 50000.0, 1.0)).await;
        
        // Should still receive valid message despite previous error
        let data = tokio::time::timeout(Duration::from_secs(1), data_rx.recv())
            .await.unwrap().unwrap();
        
        match data {
            Data::Trade(trade_tick) => {
                assert_eq!(trade_tick.instrument_id, instrument_id);
            }
            _ => panic!("Expected Trade data"),
        }
        
        // Check error statistics
        let stats = client.get_stats().await;
        assert!(stats.processing_errors > 0);
        assert!(stats.messages_processed > 0);
    }
}
```

### 3. Performance Benchmarks

#### 3.1 Throughput Benchmarks

**File**: `benches/throughput_bench.rs`

```rust
use criterion::{criterion_group, criterion_main, Criterion, BenchmarkId};
use fourotc::*;
use tokio::runtime::Runtime;

fn message_processing_benchmark(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    
    let mut group = c.benchmark_group("message_processing");
    
    for message_count in [1000, 10000, 100000].iter() {
        group.bench_with_input(
            BenchmarkId::new("trade_messages", message_count),
            message_count,
            |b, &count| {
                b.to_async(&rt).iter(|| async {
                    let mut client = create_test_client().await;
                    let (data_tx, mut data_rx) = mpsc::unbounded_channel();
                    client.set_data_channel(data_tx);
                    
                    let instrument_id = InstrumentId::from("BTCUSD.4OTC");
                    client.register_instrument(100, instrument_id).await;
                    client.connect().await.unwrap();
                    
                    let start = std::time::Instant::now();
                    
                    // Send messages
                    for i in 0..count {
                        let trade = create_test_trade_protobuf_message(100, 50000.0 + i as f64, 1.0);
                        send_protobuf_message(&client, trade).await;
                    }
                    
                    // Receive all messages
                    for _ in 0..count {
                        data_rx.recv().await.unwrap();
                    }
                    
                    let duration = start.elapsed();
                    let throughput = count as f64 / duration.as_secs_f64();
                    println!("Throughput: {:.0} messages/second", throughput);
                });
            }
        );
    }
    
    group.finish();
}

fn data_conversion_benchmark(c: &mut Criterion) {
    let mut group = c.benchmark_group("data_conversion");
    
    let venue = Venue::from("4OTC");
    let mut converter = DataConverter::new(venue);
    let instrument_id = InstrumentId::from("BTCUSD.4OTC");
    converter.register_instrument(100, instrument_id);
    
    group.bench_function("trade_conversion", |b| {
        let trade = create_test_trade_4otc_message(100, 50000.0, 1.5);
        let message = DecodedMessage::Trade(trade);
        
        b.iter(|| {
            converter.convert_message(&message).unwrap()
        })
    });
    
    group.bench_function("orderbook_conversion", |b| {
        let book = create_test_orderbook_4otc_message(100);
        let message = DecodedMessage::OrderBookSnapshot(book);
        
        b.iter(|| {
            converter.convert_message(&message).unwrap()
        })
    });
    
    group.finish();
}

criterion_group!(benches, message_processing_benchmark, data_conversion_benchmark);
criterion_main!(benches);
```

#### 3.2 Latency Benchmarks

**File**: `benches/latency_bench.rs`

```rust
use criterion::{criterion_group, criterion_main, Criterion};
use fourotc::*;
use std::time::Instant;
use tokio::runtime::Runtime;

fn end_to_end_latency_benchmark(c: &mut Criterion) {
    let rt = Runtime::new().unwrap();
    
    c.bench_function("end_to_end_trade_latency", |b| {
        b.to_async(&rt).iter(|| async {
            let mut client = create_test_client().await;
            let (data_tx, mut data_rx) = mpsc::unbounded_channel();
            client.set_data_channel(data_tx);
            
            let instrument_id = InstrumentId::from("BTCUSD.4OTC");
            client.register_instrument(100, instrument_id).await;
            client.connect().await.unwrap();
            
            // Measure end-to-end latency
            let start = Instant::now();
            
            let trade = create_test_trade_protobuf_message(100, 50000.0, 1.0);
            send_protobuf_message(&client, trade).await;
            
            let _data = data_rx.recv().await.unwrap();
            let latency = start.elapsed();
            
            // Target: < 500μs for NATS mode
            assert!(latency.as_micros() < 500);
            latency
        });
    });
}

fn conversion_latency_benchmark(c: &mut Criterion) {
    let venue = Venue::from("4OTC");
    let mut converter = DataConverter::new(venue);
    let instrument_id = InstrumentId::from("BTCUSD.4OTC");
    converter.register_instrument(100, instrument_id);
    
    c.bench_function("trade_conversion_latency", |b| {
        let trade = create_test_trade_4otc_message(100, 50000.0, 1.5);
        let message = DecodedMessage::Trade(trade);
        
        b.iter(|| {
            let start = Instant::now();
            let _result = converter.convert_message(&message).unwrap();
            let latency = start.elapsed();
            
            // Target: < 10μs for conversion
            assert!(latency.as_micros() < 10);
            latency
        })
    });
}

criterion_group!(benches, end_to_end_latency_benchmark, conversion_latency_benchmark);
criterion_main!(benches);
```

#### 3.3 Memory Usage Tests

**File**: `tests/performance/memory_tests.rs`

```rust
#[cfg(test)]
mod memory_tests {
    use super::*;
    use fourotc::*;
    use std::mem;
    
    #[test]
    fn test_memory_usage_bounds() {
        // Test that key structures have reasonable memory footprint
        assert!(mem::size_of::<FourOtcDataClient>() < 1024); // < 1KB
        assert!(mem::size_of::<DataConverter>() < 512);       // < 512B
        assert!(mem::size_of::<ClientStats>() < 256);         // < 256B
        
        println!("FourOtcDataClient size: {} bytes", mem::size_of::<FourOtcDataClient>());
        println!("DataConverter size: {} bytes", mem::size_of::<DataConverter>());
        println!("ClientStats size: {} bytes", mem::size_of::<ClientStats>());
    }
    
    #[tokio::test]
    async fn test_memory_growth_under_load() {
        let initial_memory = get_current_memory_usage();
        
        let mut client = create_test_client().await;
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        // Process many messages
        for i in 0..100000 {
            let trade = create_test_trade_protobuf_message(100, 50000.0 + i as f64, 1.0);
            send_protobuf_message(&client, trade).await;
            let _data = data_rx.recv().await.unwrap();
            
            if i % 10000 == 0 {
                let current_memory = get_current_memory_usage();
                let growth = current_memory - initial_memory;
                println!("Memory growth after {} messages: {} MB", i, growth / 1024 / 1024);
                
                // Memory growth should be bounded
                assert!(growth < 100 * 1024 * 1024); // < 100MB growth
            }
        }
        
        let final_memory = get_current_memory_usage();
        let total_growth = final_memory - initial_memory;
        println!("Total memory growth: {} MB", total_growth / 1024 / 1024);
        
        // Total growth should be reasonable
        assert!(total_growth < 100 * 1024 * 1024); // < 100MB total
    }
    
    #[tokio::test]
    async fn test_memory_cleanup() {
        let initial_memory = get_current_memory_usage();
        
        {
            let mut client = create_test_client().await;
            client.connect().await.unwrap();
            
            // Use some memory
            for i in 0..10000 {
                let instrument_id = InstrumentId::from(&format!("SYMBOL{}.4OTC", i));
                client.register_instrument(i as u32, instrument_id).await;
            }
            
            let peak_memory = get_current_memory_usage();
            assert!(peak_memory > initial_memory);
            
            client.disconnect().await.unwrap();
            client.dispose().unwrap();
        } // Client should be dropped here
        
        // Force garbage collection
        tokio::time::sleep(Duration::from_millis(100)).await;
        
        let final_memory = get_current_memory_usage();
        let cleanup_ratio = (peak_memory - final_memory) as f64 / (peak_memory - initial_memory) as f64;
        
        println!("Memory cleanup ratio: {:.2}%", cleanup_ratio * 100.0);
        
        // Should clean up most memory (at least 80%)
        assert!(cleanup_ratio > 0.8);
    }
}
```

### 4. Production Tests

#### 4.1 Load Testing

**File**: `tests/production/load_tests.rs`

```rust
#[cfg(test)]
mod load_tests {
    use super::*;
    use fourotc::*;
    use std::sync::Arc;
    use tokio::sync::Barrier;
    
    #[tokio::test]
    async fn test_concurrent_clients() {
        let client_count = 10;
        let messages_per_client = 1000;
        
        let barrier = Arc::new(Barrier::new(client_count));
        let mut handles = Vec::new();
        
        for client_id in 0..client_count {
            let barrier_clone = barrier.clone();
            
            let handle = tokio::spawn(async move {
                let mut config = FourOtcDataClientConfig::development();
                config.client_id = ClientId::from(&format!("CLIENT-{}", client_id));
                
                let mut client = FourOtcDataClient::new(config).unwrap();
                let (data_tx, mut data_rx) = mpsc::unbounded_channel();
                client.set_data_channel(data_tx);
                
                let instrument_id = InstrumentId::from("BTCUSD.4OTC");
                client.register_instrument(100, instrument_id).await;
                client.connect().await.unwrap();
                
                barrier_clone.wait().await; // Sync all clients
                
                let start = Instant::now();
                
                // Process messages concurrently
                for i in 0..messages_per_client {
                    let trade = create_test_trade_protobuf_message(100, 50000.0 + i as f64, 1.0);
                    send_protobuf_message(&client, trade).await;
                    let _data = data_rx.recv().await.unwrap();
                }
                
                let duration = start.elapsed();
                let throughput = messages_per_client as f64 / duration.as_secs_f64();
                
                println!("Client {} throughput: {:.0} msg/s", client_id, throughput);
                
                client.disconnect().await.unwrap();
                throughput
            });
            
            handles.push(handle);
        }
        
        let results: Vec<f64> = futures::future::join_all(handles)
            .await
            .into_iter()
            .map(|r| r.unwrap())
            .collect();
        
        let total_throughput: f64 = results.iter().sum();
        let avg_throughput = total_throughput / client_count as f64;
        
        println!("Total throughput: {:.0} msg/s", total_throughput);
        println!("Average per client: {:.0} msg/s", avg_throughput);
        
        // Each client should maintain good throughput
        assert!(avg_throughput > 1000.0);
        
        // Total throughput should scale reasonably
        assert!(total_throughput > 5000.0);
    }
    
    #[tokio::test]
    async fn test_sustained_load() {
        let test_duration = Duration::from_secs(60); // 1 minute test
        let target_rate = 10000; // 10k messages per second
        
        let mut client = create_test_client().await;
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        let start = Instant::now();
        let mut message_count = 0;
        let mut interval = tokio::time::interval(Duration::from_micros(100)); // 10k/sec = 100μs interval
        
        let producer_handle = tokio::spawn(async move {
            let mut i = 0;
            while start.elapsed() < test_duration {
                interval.tick().await;
                let trade = create_test_trade_protobuf_message(100, 50000.0 + i as f64, 1.0);
                send_protobuf_message(&client, trade).await;
                i += 1;
            }
            i
        });
        
        let consumer_handle = tokio::spawn(async move {
            let mut received = 0;
            while start.elapsed() < test_duration + Duration::from_secs(5) {
                if let Ok(Some(_data)) = tokio::time::timeout(Duration::from_millis(100), data_rx.recv()).await {
                    received += 1;
                } else {
                    break;
                }
            }
            received
        });
        
        let (sent, received) = tokio::try_join!(producer_handle, consumer_handle).unwrap();
        
        let actual_duration = start.elapsed();
        let send_rate = sent as f64 / actual_duration.as_secs_f64();
        let receive_rate = received as f64 / actual_duration.as_secs_f64();
        let loss_rate = (sent - received) as f64 / sent as f64;
        
        println!("Sent: {} messages at {:.0} msg/s", sent, send_rate);
        println!("Received: {} messages at {:.0} msg/s", received, receive_rate);
        println!("Loss rate: {:.2}%", loss_rate * 100.0);
        
        // Should achieve target rate
        assert!(send_rate > target_rate as f64 * 0.9); // Within 10% of target
        
        // Should have low loss rate
        assert!(loss_rate < 0.01); // < 1% loss
        
        // Should maintain good receive rate
        assert!(receive_rate > target_rate as f64 * 0.8); // At least 80% of target
    }
}
```

#### 4.2 Failover and Recovery Tests

**File**: `tests/production/failover_tests.rs`

```rust
#[cfg(test)]
mod failover_tests {
    use super::*;
    use fourotc::*;
    
    #[tokio::test]
    async fn test_nats_server_restart() {
        let nats_url = "nats://localhost:4224";
        let mut config = FourOtcDataClientConfig::development();
        config.nats.servers = vec![nats_url.to_string()];
        config.nats.max_reconnect_attempts = Some(10);
        config.nats.reconnect_delay_ms = 100;
        
        // Start NATS server
        let nats_server = start_test_nats_server("4224").await;
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        // Verify initial connection
        assert_eq!(client.get_connection_state().await, ConnectionState::Connected);
        
        // Send initial message
        send_test_message(&client, 1).await;
        let data1 = tokio::time::timeout(Duration::from_secs(1), data_rx.recv()).await.unwrap().unwrap();
        verify_trade_data(&data1, 1);
        
        // Restart NATS server
        println!("Stopping NATS server...");
        nats_server.stop().await;
        
        tokio::time::sleep(Duration::from_millis(200)).await;
        
        println!("Restarting NATS server...");
        let _new_server = start_test_nats_server("4224").await;
        
        // Wait for reconnection
        let mut reconnected = false;
        for _ in 0..50 { // 5 seconds max
            tokio::time::sleep(Duration::from_millis(100)).await;
            if client.get_connection_state().await == ConnectionState::Connected {
                reconnected = true;
                break;
            }
        }
        
        assert!(reconnected, "Client should reconnect after server restart");
        
        // Verify functionality after reconnection
        send_test_message(&client, 2).await;
        let data2 = tokio::time::timeout(Duration::from_secs(1), data_rx.recv()).await.unwrap().unwrap();
        verify_trade_data(&data2, 2);
        
        let stats = client.get_stats().await;
        println!("Reconnection stats: {:?}", stats);
    }
    
    #[tokio::test]
    async fn test_multiple_server_failover() {
        let servers = vec![
            "nats://localhost:4225",
            "nats://localhost:4226",
            "nats://localhost:4227",
        ];
        
        let mut config = FourOtcDataClientConfig::development();
        config.nats.servers = servers.iter().map(|s| s.to_string()).collect();
        config.nats.max_reconnect_attempts = Some(20);
        
        // Start all servers
        let mut nats_servers = Vec::new();
        for (i, _) in servers.iter().enumerate() {
            let port = (4225 + i).to_string();
            nats_servers.push(start_test_nats_server(&port).await);
        }
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        // Test failover through servers
        for i in 0..3 {
            println!("Testing failover step {}", i);
            
            // Verify connection and functionality
            assert_eq!(client.get_connection_state().await, ConnectionState::Connected);
            
            send_test_message(&client, i + 1).await;
            let data = tokio::time::timeout(Duration::from_secs(1), data_rx.recv()).await.unwrap().unwrap();
            verify_trade_data(&data, i + 1);
            
            // Stop current primary server (except last iteration)
            if i < 2 {
                nats_servers[i].stop().await;
                
                // Wait for failover to next server
                tokio::time::sleep(Duration::from_secs(2)).await;
            }
        }
        
        let stats = client.get_stats().await;
        println!("Multi-server failover stats: {:?}", stats);
        
        // Should maintain good success rate despite failovers
        assert!(stats.success_rate() > 0.9);
    }
    
    #[tokio::test]
    async fn test_network_partition_recovery() {
        let mut config = FourOtcDataClientConfig::development();
        config.nats.max_reconnect_attempts = Some(30);
        config.nats.reconnect_delay_ms = 200;
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        // Normal operation
        send_test_message(&client, 1).await;
        let _data1 = data_rx.recv().await.unwrap();
        
        // Simulate network partition
        println!("Simulating network partition...");
        simulate_network_partition(&client).await;
        
        // During partition, messages should fail
        let partition_start = Instant::now();
        let mut failed_sends = 0;
        
        while partition_start.elapsed() < Duration::from_secs(5) {
            if send_test_message(&client, 999).await.is_err() {
                failed_sends += 1;
            }
            tokio::time::sleep(Duration::from_millis(100)).await;
        }
        
        assert!(failed_sends > 0, "Should have failed sends during partition");
        
        // Restore network
        println!("Restoring network...");
        restore_network(&client).await;
        
        // Wait for recovery
        let mut recovered = false;
        for _ in 0..50 {
            tokio::time::sleep(Duration::from_millis(100)).await;
            if client.get_connection_state().await == ConnectionState::Connected {
                recovered = true;
                break;
            }
        }
        
        assert!(recovered, "Should recover from network partition");
        
        // Verify functionality after recovery
        send_test_message(&client, 2).await;
        let data2 = tokio::time::timeout(Duration::from_secs(1), data_rx.recv()).await.unwrap().unwrap();
        verify_trade_data(&data2, 2);
    }
}
```

#### 4.3 Long-Running Stability Tests

**File**: `tests/production/stability_tests.rs`

```rust
#[cfg(test)]
mod stability_tests {
    use super::*;
    use fourotc::*;
    
    #[tokio::test]
    #[ignore] // Long-running test
    async fn test_24_hour_stability() {
        let test_duration = Duration::from_secs(24 * 60 * 60); // 24 hours
        let check_interval = Duration::from_secs(60); // Check every minute
        
        let mut client = create_test_client().await;
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        client.connect().await.unwrap();
        
        let start = Instant::now();
        let mut check_count = 0;
        let mut total_messages = 0;
        let mut error_count = 0;
        
        while start.elapsed() < test_duration {
            // Send periodic messages
            for i in 0..10 {
                match send_test_message(&client, total_messages + i).await {
                    Ok(_) => {
                        match tokio::time::timeout(Duration::from_secs(1), data_rx.recv()).await {
                            Ok(Some(_)) => total_messages += 1,
                            _ => error_count += 1,
                        }
                    }
                    Err(_) => error_count += 1,
                }
            }
            
            // Periodic health checks
            if start.elapsed() > check_interval * check_count {
                check_count += 1;
                
                let connection_state = client.get_connection_state().await;
                let stats = client.get_stats().await;
                
                println!("Hour {}: Connection: {:?}, Messages: {}, Errors: {}, Success Rate: {:.2}%",
                    check_count / 60,
                    connection_state,
                    total_messages,
                    error_count,
                    stats.success_rate() * 100.0
                );
                
                // Health checks
                assert_eq!(connection_state, ConnectionState::Connected);
                assert!(stats.success_rate() > 0.95); // 95% success rate
                
                // Memory growth check
                let current_memory = get_current_memory_usage();
                assert!(current_memory < 200 * 1024 * 1024); // < 200MB
            }
            
            tokio::time::sleep(Duration::from_secs(1)).await;
        }
        
        println!("24-hour test completed:");
        println!("Total messages: {}", total_messages);
        println!("Error count: {}", error_count);
        println!("Error rate: {:.2}%", error_count as f64 / total_messages as f64 * 100.0);
        
        let final_stats = client.get_stats().await;
        assert!(final_stats.success_rate() > 0.95);
        assert!(error_count < total_messages / 20); // < 5% errors
    }
    
    #[tokio::test]
    async fn test_memory_leak_detection() {
        let iterations = 1000;
        let messages_per_iteration = 100;
        
        let initial_memory = get_current_memory_usage();
        let mut memory_samples = Vec::new();
        
        for iteration in 0..iterations {
            let mut client = create_test_client().await;
            let (data_tx, mut data_rx) = mpsc::unbounded_channel();
            client.set_data_channel(data_tx);
            
            let instrument_id = InstrumentId::from("BTCUSD.4OTC");
            client.register_instrument(100, instrument_id).await;
            client.connect().await.unwrap();
            
            // Process messages
            for i in 0..messages_per_iteration {
                send_test_message(&client, i).await;
                let _data = data_rx.recv().await.unwrap();
            }
            
            client.disconnect().await.unwrap();
            client.dispose().unwrap();
            
            // Sample memory every 100 iterations
            if iteration % 100 == 0 {
                // Force garbage collection
                tokio::time::sleep(Duration::from_millis(10)).await;
                
                let current_memory = get_current_memory_usage();
                memory_samples.push(current_memory);
                
                println!("Iteration {}: Memory usage: {} MB", 
                    iteration, 
                    (current_memory - initial_memory) / 1024 / 1024
                );
            }
        }
        
        // Analyze memory growth trend
        let first_quarter = &memory_samples[0..memory_samples.len()/4];
        let last_quarter = &memory_samples[memory_samples.len()*3/4..];
        
        let avg_first: u64 = first_quarter.iter().sum::<u64>() / first_quarter.len() as u64;
        let avg_last: u64 = last_quarter.iter().sum::<u64>() / last_quarter.len() as u64;
        
        let growth_ratio = avg_last as f64 / avg_first as f64;
        
        println!("Memory growth ratio: {:.2}", growth_ratio);
        
        // Memory should not grow significantly over time
        assert!(growth_ratio < 1.5, "Memory growth suggests potential leak");
        
        let final_memory = get_current_memory_usage();
        let total_growth = final_memory - initial_memory;
        
        println!("Total memory growth: {} MB", total_growth / 1024 / 1024);
        
        // Total growth should be bounded
        assert!(total_growth < 50 * 1024 * 1024); // < 50MB growth
    }
    
    #[tokio::test]
    async fn test_connection_churn_stability() {
        let cycles = 100;
        let messages_per_cycle = 50;
        
        let mut successful_cycles = 0;
        let mut total_messages = 0;
        
        for cycle in 0..cycles {
            let mut client = create_test_client().await;
            let (data_tx, mut data_rx) = mpsc::unbounded_channel();
            client.set_data_channel(data_tx);
            
            let instrument_id = InstrumentId::from("BTCUSD.4OTC");
            client.register_instrument(100, instrument_id).await;
            
            match client.connect().await {
                Ok(_) => {
                    let mut cycle_messages = 0;
                    
                    for i in 0..messages_per_cycle {
                        if send_test_message(&client, i).await.is_ok() {
                            if let Ok(Some(_)) = tokio::time::timeout(Duration::from_millis(100), data_rx.recv()).await {
                                cycle_messages += 1;
                                total_messages += 1;
                            }
                        }
                    }
                    
                    if cycle_messages > messages_per_cycle / 2 {
                        successful_cycles += 1;
                    }
                    
                    let _ = client.disconnect().await;
                    client.dispose().unwrap();
                    
                    if cycle % 10 == 0 {
                        println!("Completed {} cycles, {} messages", cycle + 1, total_messages);
                    }
                }
                Err(e) => {
                    println!("Connection failed in cycle {}: {}", cycle, e);
                }
            }
            
            // Small delay between cycles
            tokio::time::sleep(Duration::from_millis(10)).await;
        }
        
        let success_rate = successful_cycles as f64 / cycles as f64;
        
        println!("Connection churn test results:");
        println!("Successful cycles: {}/{} ({:.1}%)", successful_cycles, cycles, success_rate * 100.0);
        println!("Total messages processed: {}", total_messages);
        
        // Should handle connection churn gracefully
        assert!(success_rate > 0.9); // 90% of cycles should succeed
        assert!(total_messages > cycles * messages_per_cycle / 2); // At least 50% of messages
    }
}
```

### 5. Security Tests

#### 5.1 Authentication and Authorization Tests

**File**: `tests/security/auth_tests.rs`

```rust
#[cfg(test)]
mod auth_tests {
    use super::*;
    use fourotc::*;
    
    #[tokio::test]
    async fn test_nats_token_authentication() {
        let mut config = FourOtcDataClientConfig::development();
        config.nats.auth_token = Some("valid_token".to_string());
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        
        // Should connect successfully with valid token
        assert!(client.connect().await.is_ok());
        assert_eq!(client.get_connection_state().await, ConnectionState::Connected);
        
        client.disconnect().await.unwrap();
    }
    
    #[tokio::test]
    async fn test_invalid_authentication() {
        let mut config = FourOtcDataClientConfig::development();
        config.nats.auth_token = Some("invalid_token".to_string());
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        
        // Should fail to connect with invalid token
        let result = client.connect().await;
        assert!(result.is_err());
        assert_eq!(client.get_connection_state().await, ConnectionState::Failed);
    }
    
    #[tokio::test]
    async fn test_unauthorized_subscription() {
        let mut config = FourOtcDataClientConfig::development();
        config.nats.auth_token = Some("limited_permissions_token".to_string());
        
        let mut client = FourOtcDataClient::new(config).unwrap();
        client.connect().await.unwrap();
        
        let instrument_id = InstrumentId::from("RESTRICTED.4OTC");
        client.register_instrument(999, instrument_id).await;
        
        let cmd = SubscribeTrades {
            instrument_id,
            client_id: Some(client.client_id()),
            venue: Some(client.venue().unwrap()),
            command_id: uuid::Uuid::new_v4().into(),
            ts_init: get_atomic_clock_realtime().get_time_ns(),
            params: None,
        };
        
        // Should fail to subscribe to restricted instrument
        let result = client.subscribe_trades(&cmd);
        assert!(result.is_err());
    }
}
```

#### 5.2 Data Validation and Sanitization Tests

**File**: `tests/security/validation_tests.rs`

```rust
#[cfg(test)]
mod validation_tests {
    use super::*;
    use fourotc::*;
    
    #[test]
    fn test_price_validation() {
        // Valid prices
        assert!(DataConverter::normalize_price(100.50, 2).is_ok());
        assert!(DataConverter::normalize_price(0.0001, 8).is_ok());
        assert!(DataConverter::normalize_price(0.0, 2).is_ok());
        
        // Invalid prices
        assert!(DataConverter::normalize_price(f64::NAN, 2).is_err());
        assert!(DataConverter::normalize_price(f64::INFINITY, 2).is_err());
        assert!(DataConverter::normalize_price(f64::NEG_INFINITY, 2).is_err());
        assert!(DataConverter::normalize_price(-1.0, 2).is_err());
    }
    
    #[test]
    fn test_quantity_validation() {
        // Valid quantities
        assert!(DataConverter::normalize_quantity(100.50, 2).is_ok());
        assert!(DataConverter::normalize_quantity(0.0001, 8).is_ok());
        assert!(DataConverter::normalize_quantity(0.0, 2).is_ok());
        
        // Invalid quantities
        assert!(DataConverter::normalize_quantity(f64::NAN, 2).is_err());
        assert!(DataConverter::normalize_quantity(f64::INFINITY, 2).is_err());
        assert!(DataConverter::normalize_quantity(f64::NEG_INFINITY, 2).is_err());
        assert!(DataConverter::normalize_quantity(-1.0, 2).is_err());
    }
    
    #[test]
    fn test_config_validation() {
        // Valid configuration
        let mut config = FourOtcDataClientConfig::development();
        assert!(config.validate().is_ok());
        
        // Invalid configurations
        config.buffer_size = 0;
        assert!(config.validate().is_err());
        
        config.buffer_size = 10000;
        config.heartbeat_interval_secs = 0;
        assert!(config.validate().is_err());
        
        config.heartbeat_interval_secs = 10;
        config.nats.servers.clear();
        assert!(config.validate().is_err());
    }
    
    #[tokio::test]
    async fn test_malformed_message_handling() {
        let mut client = create_test_client().await;
        let (data_tx, mut data_rx) = mpsc::unbounded_channel();
        client.set_data_channel(data_tx);
        client.connect().await.unwrap();
        
        let initial_stats = client.get_stats().await;
        
        // Send various malformed messages
        let malformed_messages = vec![
            vec![], // Empty message
            vec![0xFF; 100], // Random bytes
            b"not_sbe_format".to_vec(), // Text data
            vec![0x00; 1000], // Null bytes
        ];
        
        for malformed in malformed_messages {
            send_raw_message(&client, malformed).await;
        }
        
        // Wait for processing
        tokio::time::sleep(Duration::from_millis(100)).await;
        
        // Should not receive any data from malformed messages
        let timeout_result = tokio::time::timeout(Duration::from_millis(50), data_rx.recv()).await;
        assert!(timeout_result.is_err());
        
        let final_stats = client.get_stats().await;
        
        // Error count should increase
        assert!(final_stats.processing_errors > initial_stats.processing_errors);
        
        // Client should still be functional
        assert_eq!(client.get_connection_state().await, ConnectionState::Connected);
        
        // Should still process valid messages
        let instrument_id = InstrumentId::from("BTCUSD.4OTC");
        client.register_instrument(100, instrument_id).await;
        send_test_message(&client, 1).await;
        
        let data = tokio::time::timeout(Duration::from_secs(1), data_rx.recv()).await.unwrap().unwrap();
        verify_trade_data(&data, 1);
    }
    
    #[test]
    fn test_instrument_id_validation() {
        let venue = Venue::from("4OTC");
        let mut converter = DataConverter::new(venue);
        
        // Valid security IDs
        let valid_ids = [1, 100, 999, 1000, 9999];
        for id in &valid_ids {
            let instrument_id = InstrumentId::from(&format!("TEST{}.4OTC", id));
            converter.register_instrument(*id, instrument_id);
            assert!(converter.get_instrument_id(*id as i32).is_ok());
        }
        
        // Invalid security ID (not registered)
        assert!(converter.get_instrument_id(99999).is_err());
        
        // Edge case: security ID 0
        assert!(converter.get_instrument_id(0).is_err());
    }
}
```

## Test Execution Strategy

### 1. Test Categorization

```bash
# Unit tests - Fast, no external dependencies
cargo test -p fourotc unit --lib

# Integration tests - Require NATS server
cargo test -p fourotc integration --features integration-tests

# Performance benchmarks
cargo bench -p fourotc

# Production tests - Long-running, comprehensive
cargo test -p fourotc production --release --features production-tests

# Security tests
cargo test -p fourotc security --features security-tests
```

### 2. Continuous Integration Pipeline

**File**: `.github/workflows/fourotc_tests.yml`

```yaml
name: 4OTC Adapter Tests

on:
  push:
    branches: [ main, develop ]
    paths: [ 'crates/adapters/fourotc/**' ]
  pull_request:
    branches: [ main, develop ]
    paths: [ 'crates/adapters/fourotc/**' ]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Rust
      uses: actions-rs/toolchain@v1
      with:
        toolchain: 1.89.0
        override: true
        components: rustfmt, clippy
    
    - name: Check formatting
      run: cargo fmt -p fourotc -- --check
    
    - name: Clippy
      run: cargo clippy -p fourotc -- -D warnings
    
    - name: Unit tests
      run: cargo test -p fourotc unit --lib
  
  integration-tests:
    runs-on: ubuntu-latest
    services:
      nats:
        image: nats:latest
        ports:
          - 4222:4222
        options: >-
          --health-cmd "wget --no-verbose --tries=1 --spider http://localhost:8222/varz || exit 1"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Rust
      uses: actions-rs/toolchain@v1
      with:
        toolchain: 1.89.0
        override: true
    
    - name: Integration tests
      run: cargo test -p fourotc integration --features integration-tests
      env:
        NATS_URL: nats://localhost:4222
  
  performance-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    
    - name: Setup Rust
      uses: actions-rs/toolchain@v1
      with:
        toolchain: 1.89.0
        override: true
    
    - name: Performance benchmarks
      run: cargo bench -p fourotc --features benchmarks
    
    - name: Upload benchmark results
      uses: actions/upload-artifact@v3
      with:
        name: benchmark-results
        path: target/criterion/
```

### 3. Local Testing Guide

#### Prerequisites
```bash
# Install Rust 1.89.0
rustup toolchain install 1.89.0
rustup default 1.89.0

# Install NATS server
# macOS
brew install nats-server

# Linux
curl -L https://github.com/nats-io/nats-server/releases/download/v2.9.0/nats-server-v2.9.0-linux-amd64.zip -o nats.zip
unzip nats.zip && sudo mv nats-server-v2.9.0-linux-amd64/nats-server /usr/local/bin/

# Start NATS server
nats-server --port 4222
```

#### Running Tests
```bash
# Navigate to project root
cd /Users/dima/validalpha/nautilus_trader

# Run all unit tests
cargo test -p fourotc unit

# Run integration tests (requires NATS)
cargo test -p fourotc integration --features integration-tests

# Run specific test
cargo test -p fourotc test_data_converter_creation

# Run with output
cargo test -p fourotc -- --nocapture

# Run benchmarks
cargo bench -p fourotc

# Run with coverage (requires cargo-tarpaulin)
cargo install cargo-tarpaulin
cargo tarpaulin -p fourotc --out html
```

### 4. Test Data and Fixtures

#### Test Data Setup

**File**: `tests/common/fixtures.rs`

```rust
use fourotc::proto::{self, MarketDataMessage};
use prost::Message;

pub fn create_test_trade_protobuf_message(security_id: i32, price: f64, quantity: f64) -> Vec<u8> {
    let trade = proto::Trade {
        security_id,
        venue_id: 1,
        price,
        quantity,
        timestamp: 1234567890000,
        trade_id: format!("trade_{}", security_id),
        aggressor_side: proto::AggressorSide::AggressorBuy as i32,
        conditions: vec![],
        additional_info: vec![],
    };
    
    let message = MarketDataMessage {
        message_type: Some(proto::market_data_message::MessageType::Trade(trade)),
        timestamp_nanos: 1234567890000,
        message_id: format!("msg_{}", security_id),
    };
    
    message.encode_to_vec()
}

pub fn create_test_orderbook_protobuf_message(security_id: i32) -> Vec<u8> {
    let snapshot = proto::OrderBookSnapshot {
        security_id,
        venue_id: 1,
        timestamp: 1234567890000,
        bids: vec![
            proto::OrderBookLevel { price: 50000.0, quantity: 1.5, order_count: 1, min_qty: 0.0, additional_info: vec![] },
            proto::OrderBookLevel { price: 49999.0, quantity: 2.0, order_count: 1, min_qty: 0.0, additional_info: vec![] },
            proto::OrderBookLevel { price: 49998.0, quantity: 1.0, order_count: 1, min_qty: 0.0, additional_info: vec![] },
        ],
        asks: vec![
            proto::OrderBookLevel { price: 50001.0, quantity: 1.0, order_count: 1, min_qty: 0.0, additional_info: vec![] },
            proto::OrderBookLevel { price: 50002.0, quantity: 0.5, order_count: 1, min_qty: 0.0, additional_info: vec![] },
            proto::OrderBookLevel { price: 50003.0, quantity: 2.5, order_count: 1, min_qty: 0.0, additional_info: vec![] },
        ],
    };
    
    let message = MarketDataMessage {
        message_type: Some(proto::market_data_message::MessageType::OrderBookSnapshot(snapshot)),
        timestamp_nanos: 1234567890000,
        message_id: format!("book_{}", security_id),
    };
    
    message.encode_to_vec()
}

pub async fn create_test_client() -> FourOtcDataClient {
    let mut config = FourOtcDataClientConfig::development();
    config.nats.servers = vec!["nats://localhost:4222".to_string()];
    FourOtcDataClient::new(config).unwrap()
}
```

## Test Coverage Goals

### Coverage Targets
- **Unit Tests**: 95% code coverage
- **Integration Tests**: 100% critical path coverage
- **Error Paths**: 100% error condition coverage
- **Performance**: All performance targets validated

### Quality Gates
1. **All unit tests pass** (blocking)
2. **All integration tests pass** (blocking)
3. **Code coverage > 90%** (blocking)
4. **No clippy warnings** (blocking)
5. **Performance benchmarks pass** (non-blocking, monitored)
6. **Memory usage within bounds** (monitored)

## Reporting and Monitoring

### Test Results Dashboard
- **Jenkins/GitHub Actions**: Automated test execution
- **Coverage Reports**: HTML coverage reports generated
- **Performance Trends**: Benchmark result tracking
- **Flaky Test Detection**: Test stability monitoring

### Production Monitoring
- **Health Checks**: Connection state monitoring
- **Performance Metrics**: Latency and throughput tracking
- **Error Rates**: Processing error monitoring
- **Resource Usage**: Memory and CPU monitoring

## Conclusion

This comprehensive test plan ensures the 4OTC adapter meets all functional, performance, and reliability requirements. The multi-layered testing approach provides confidence in the adapter's production readiness while establishing a foundation for ongoing quality assurance.

Key benefits of this test plan:
- **Complete Coverage**: Unit, integration, performance, and production testing
- **Automation**: CI/CD pipeline integration for continuous validation
- **Performance Validation**: Benchmarks ensure performance targets are met
- **Production Readiness**: Load testing and failover scenarios validate real-world usage
- **Security Assurance**: Authentication and data validation testing
- **Maintainability**: Clear test organization and documentation

The test plan provides a solid foundation for validating the 4OTC adapter's functionality and ensuring its successful deployment in production environments.