# 4OTC Adapter for Nautilus Trader

This adapter provides integration between [Nautilus Trader](https://nautilustrader.io) and 4OTC market data feeds through NATS messaging.

## Overview

The 4OTC adapter enables Nautilus Trader to consume real-time market data from 4OTC trading venues through a NATS-based message broker architecture. This design provides:

- **Scalability**: NATS messaging enables horizontal scaling and load distribution
- **Reliability**: Message persistence and replay capabilities through JetStream
- **Performance**: High-throughput, low-latency message delivery
- **Flexibility**: Support for multiple data formats (JSON, Protocol Buffers)

## Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────────┐
│ 4OTC WebSocket  │    │     NATS     │    │  Nautilus Trader    │
│    Gateway      │───▶│   Message    │───▶│   4OTC Adapter     │
│                 │    │   Broker     │    │                     │
└─────────────────┘    └──────────────┘    └─────────────────────┘
        │                       │                      │
        │                       │                      │
        ▼                       ▼                      ▼
┌─────────────────┐    ┌──────────────┐    ┌─────────────────────┐
│ SBE Message     │    │ NATS Subjects│    │ Nautilus Data Types │
│ Decoding        │    │              │    │                     │
│                 │    │ - Trades     │    │ - TradeTick         │
│ - OrderBook     │    │ - Books      │    │ - OrderBookDepth10  │
│ - Trades        │    │ - Security   │    │ - QuoteTick         │
│ - Securities    │    │ - Status     │    │ - InstrumentStatus  │
└─────────────────┘    └──────────────┘    └─────────────────────┘
```

## Features

### Market Data Support
- **Order Book Data**: Level 2 snapshots and incremental updates
- **Trade Data**: Real-time trade executions with aggressor side
- **Security Definitions**: Instrument metadata and configuration
- **Security Status**: Trading status updates
- **Heartbeats**: Connection health monitoring

### Technical Features
- **NATS Integration**: Native NATS client with connection pooling
- **Message Conversion**: Automatic conversion from 4OTC SBE to Nautilus types
- **Error Handling**: Comprehensive error handling and recovery
- **Statistics**: Built-in performance and connection statistics
- **Configuration**: Flexible configuration for different environments
- **Python Bindings**: Optional Python API for integration

## Quick Start

### Prerequisites

- Rust 1.89.0 or later
- NATS server running (local or remote)
- Access to 4OTC market data feeds

### Installation

Add the adapter to your `Cargo.toml`:

```toml
[dependencies]
fourotc = { path = "path/to/nautilus_trader/crates/adapters/fourotc" }
```

### Basic Usage

```rust
use fourotc::{FourOtcDataClient, FourOtcDataClientConfig};
use nautilus_model::identifiers::{ClientId, Venue, InstrumentId};
use tokio::sync::mpsc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Create configuration
    let config = FourOtcDataClientConfig::new(
        ClientId::from("FOUROTC-001"),
        Venue::from("4OTC"),
    );
    
    // Create data client
    let mut client = FourOtcDataClient::new(config)?;
    
    // Set up data channel
    let (data_tx, mut data_rx) = mpsc::unbounded_channel();
    client.set_data_channel(data_tx);
    
    // Register instruments
    let instrument_id = InstrumentId::from("BTCUSD.4OTC");
    client.register_instrument(100, instrument_id).await;
    
    // Connect and start
    client.start()?;
    client.connect().await?;
    
    // Subscribe to market data
    // ... subscription code ...
    
    // Process incoming data
    while let Some(data) = data_rx.recv().await {
        println!("Received: {:?}", data);
    }
    
    Ok(())
}
```

## Configuration

### Basic Configuration

```rust
use fourotc::config::{FourOtcDataClientConfig, NatsConfig};

let mut config = FourOtcDataClientConfig::new(
    ClientId::from("MY-CLIENT"),
    Venue::from("4OTC"),
);

// Configure NATS connection
config.nats.servers = vec!["nats://localhost:4222".to_string()];
config.nats.subject_prefix = "market.4otc".to_string();

// Configure subscriptions
config.subscriptions.trades = true;
config.subscriptions.order_book_snapshots = true;
config.subscriptions.security_definitions = true;
```

### Environment-Specific Configurations

#### Development
```rust
let config = FourOtcDataClientConfig::development();
```

#### Production
```rust
let config = FourOtcDataClientConfig::production();
```

### Advanced Configuration

```rust
use fourotc::config::{DataFormat, JetStreamConsumerConfig, DeliverPolicy};

let mut config = FourOtcDataClientConfig::production();

// Use Protocol Buffers for better performance
config.data_format = DataFormat::Protobuf;

// Enable JetStream for message persistence
config.nats.enable_jetstream = true;
config.nats.jetstream_consumer = Some(JetStreamConsumerConfig {
    stream_name: "4OTC_MARKET_DATA".to_string(),
    consumer_name: Some("nautilus-consumer".to_string()),
    deliver_policy: DeliverPolicy::All,
    ..Default::default()
});

// Optimize performance
config.buffer_size = 100000;
config.enable_message_filtering = true;
```

## NATS Subject Structure

The adapter uses a hierarchical NATS subject structure:

```
market.4otc.
├── heartbeat                    # System heartbeats
├── request.
│   ├── accept.<request_id>     # Request acceptances
│   └── reject.<request_id>     # Request rejections
├── snapshot.level2.<venue>.<security>  # Order book snapshots
├── trades.<venue>              # Trade executions
├── security.
│   ├── definition.<security>   # Security definitions
│   └── status.<security>       # Security status updates
└── client.disconnect           # Client disconnect notifications
```

### Subscription Examples

```rust
// Subscribe to all trades from venue 1
"market.4otc.trades.1"

// Subscribe to order book for specific security
"market.4otc.snapshot.level2.1.100"

// Subscribe to all security definitions
"market.4otc.security.definition.*"

// Subscribe to everything
"market.4otc.>"
```

## Data Types

### Supported Nautilus Data Types

| 4OTC Message Type | Nautilus Data Type | Description |
|-------------------|-------------------|-------------|
| OrderBookSnapshot | OrderBookDepth10 | Level 2 order book with up to 10 levels |
| Trade | TradeTick | Individual trade execution |
| SecurityDefinition | Custom | Instrument metadata (handled during setup) |
| SecurityStatus | InstrumentStatus | Trading status updates |

### Message Conversion

The adapter automatically converts 4OTC SBE messages to Nautilus data types:

```rust
// 4OTC Trade message becomes Nautilus TradeTick
let trade_tick = TradeTick::new(
    instrument_id,
    price,
    quantity,
    aggressor_side,
    trade_id,
    ts_event,
    ts_init,
);

// 4OTC OrderBook becomes Nautilus OrderBookDepth10
let depth = OrderBookDepth10::new(
    instrument_id,
    bids,  // Array of 10 bid levels
    asks,  // Array of 10 ask levels
    ts_event,
    ts_init,
);
```

## Testing

### Running the Test Client

The adapter includes a standalone test client:

```bash
# Build the test client
cargo build --bin fourotc_data_client

# Run with default settings
./target/debug/fourotc_data_client

# Run with custom configuration
./target/debug/fourotc_data_client \
  --nats-url nats://my-nats-server:4222 \
  --instruments "BTCUSD.4OTC,ETHUSD.4OTC" \
  --debug
```

### Unit Tests

```bash
# Run all tests
cargo test -p fourotc

# Run with output
cargo test -p fourotc -- --nocapture

# Run specific test
cargo test -p fourotc test_data_converter
```

### Integration Tests

```bash
# Requires running NATS server
docker run -p 4222:4222 nats:latest

# Run integration tests
cargo test -p fourotc --features integration-tests
```

## Monitoring and Observability

### Statistics

The client provides built-in statistics:

```rust
let stats = client.get_stats().await;
println!("Messages received: {}", stats.messages_received);
println!("Success rate: {:.2}%", stats.success_rate() * 100.0);
println!("Error rate: {:.2}%", stats.error_rate() * 100.0);
```

### Health Checks

```rust
let connection_state = client.get_connection_state().await;
match connection_state {
    ConnectionState::Connected => println!("Client is healthy"),
    ConnectionState::Disconnected => println!("Client is disconnected"),
    ConnectionState::Failed => println!("Connection failed"),
    _ => println!("Connection state: {}", connection_state),
}
```

### Logging

The adapter uses the `tracing` crate for structured logging:

```rust
use tracing::{info, warn, error};
use tracing_subscriber;

// Initialize logging
tracing_subscriber::fmt::init();

// Log levels are controlled by RUST_LOG environment variable
// RUST_LOG=fourotc=debug cargo run
```

## Error Handling

### Error Types

The adapter defines comprehensive error types:

```rust
use fourotc::enums::FourOtcError;

match result {
    Err(FourOtcError::Connection(msg)) => {
        eprintln!("Connection error: {}", msg);
    }
    Err(FourOtcError::MessageParsing(msg)) => {
        eprintln!("Message parsing error: {}", msg);
    }
    Err(FourOtcError::DataConversion(msg)) => {
        eprintln!("Data conversion error: {}", msg);
    }
    _ => {}
}
```

### Retry Logic

The client includes automatic retry logic:

```rust
// Configure retry behavior
config.nats.max_reconnect_attempts = Some(10);
config.nats.reconnect_delay_ms = 1000;  // Start with 1 second
```

## Performance Considerations

### Throughput Optimization

```rust
// Increase buffer sizes for high-throughput scenarios
config.buffer_size = 100000;

// Enable message filtering
config.enable_message_filtering = true;

// Use Protocol Buffers for better serialization performance
config.data_format = DataFormat::Protobuf;
```

### Memory Management

```rust
// The adapter uses zero-copy parsing where possible
// Large order book snapshots are boxed to avoid stack overflow
Data::Depth10(Box::new(depth))
```

### Connection Pooling

```rust
// NATS connection pooling is handled automatically
// Pool size can be configured
config.nats.pool_size = Some(4);
```

## Production Deployment

### NATS Cluster Setup

For production deployments, use a NATS cluster:

```yaml
# docker-compose.yml
version: '3.8'
services:
  nats-1:
    image: nats:latest
    command: 
      - '--cluster_name=nats-cluster'
      - '--cluster=nats://0.0.0.0:6222'
      - '--routes=nats://nats-2:6222,nats://nats-3:6222'
      - '--jetstream'
    ports:
      - "4222:4222"
      - "6222:6222"
      - "8222:8222"
  
  nats-2:
    image: nats:latest
    command:
      - '--cluster_name=nats-cluster'
      - '--cluster=nats://0.0.0.0:6222'
      - '--routes=nats://nats-1:6222,nats://nats-3:6222'
      - '--jetstream'
  
  nats-3:
    image: nats:latest
    command:
      - '--cluster_name=nats-cluster'
      - '--cluster=nats://0.0.0.0:6222'
      - '--routes=nats://nats-1:6222,nats://nats-2:6222'
      - '--jetstream'
```

### Configuration for Production

```rust
let mut config = FourOtcDataClientConfig::production();

// Use multiple NATS servers for redundancy
config.nats.servers = vec![
    "nats://nats-1:4222".to_string(),
    "nats://nats-2:4222".to_string(),
    "nats://nats-3:4222".to_string(),
];

// Enable JetStream for persistence
config.nats.enable_jetstream = true;

// Optimize for production workloads
config.buffer_size = 100000;
config.heartbeat_interval_secs = 30;
config.enable_message_filtering = true;
```

## Troubleshooting

### Common Issues

#### Connection Problems
```
Error: NATS connection failed: no servers available for connection
```
- Verify NATS server is running and accessible
- Check network connectivity and firewall rules
- Verify server URLs in configuration

#### Message Parsing Errors
```
Error: Message parsing error: Invalid JSON format
```
- Check message format configuration (JSON vs Protobuf)
- Verify 4OTC adapter is publishing correct format
- Enable debug logging to see raw messages

#### High Memory Usage
```
Warning: Buffer size exceeded, dropping messages
```
- Increase buffer size: `config.buffer_size = 200000`
- Enable message filtering: `config.enable_message_filtering = true`
- Consider using Protocol Buffers for smaller messages

### Debug Mode

Enable debug mode for detailed logging:

```rust
let mut config = FourOtcDataClientConfig::development();
config.debug_mode = true;
```

Or set environment variable:
```bash
RUST_LOG=fourotc=debug cargo run
```

### Performance Monitoring

```rust
// Monitor performance in production
tokio::spawn(async move {
    let mut interval = tokio::time::interval(Duration::from_secs(30));
    loop {
        interval.tick().await;
        let stats = client.get_stats().await;
        if stats.error_rate() > 0.1 {  // More than 10% errors
            log::warn!("High error rate detected: {:.2}%", stats.error_rate() * 100.0);
        }
    }
});
```

## Future Enhancements

### Planned Features

1. **Direct WebSocket Integration**: Bypass NATS for ultra-low latency
2. **Advanced Filtering**: Server-side message filtering
3. **Compression**: Message compression for bandwidth optimization
4. **Metrics Export**: Prometheus metrics export
5. **Admin API**: REST API for runtime configuration

### Roadmap

- **Phase 1**: NATS-based integration (✅ Complete)
- **Phase 2**: Direct WebSocket integration (Planned)
- **Phase 3**: Advanced features and optimizations (Future)

## Contributing

### Development Setup

1. Clone the repository
2. Install Rust 1.89.0 or later
3. Run NATS server locally
4. Run tests: `cargo test -p fourotc`

### Code Style

The project follows Rust standard formatting:

```bash
cargo fmt
cargo clippy
```

### Adding New Features

1. Add tests for new functionality
2. Update documentation
3. Follow existing error handling patterns
4. Ensure backward compatibility

## License

This adapter is part of Nautilus Trader and is licensed under the GNU Lesser General Public License Version 3.0 (LGPL-3.0).

## Support

For issues and questions:

- Create an issue on the [Nautilus Trader GitHub repository](https://github.com/nautechsystems/nautilus_trader)
- Join the [Nautilus Trader Discord](https://discord.gg/nautilus-trader)
- Check the [Nautilus Trader documentation](https://nautilustrader.io/docs)

## Acknowledgments

This adapter integrates with the 4OTC market data infrastructure and builds upon the excellent work of the Nautilus Trader team in creating a high-performance trading platform.