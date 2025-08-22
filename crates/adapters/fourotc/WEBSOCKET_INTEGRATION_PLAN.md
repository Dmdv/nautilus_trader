# Direct WebSocket Integration Plan for 4OTC Adapter

## Overview

This document outlines the plan for implementing direct WebSocket connectivity to 4OTC market data feeds as a future enhancement to the current NATS-based architecture. The direct integration will provide ultra-low latency market data access while maintaining compatibility with the existing system.

## Current Architecture vs Future Architecture

### Current NATS-Based Architecture
```
4OTC WebSocket → SBE Decoder → NATS Publisher → NATS Broker → Nautilus 4OTC Adapter → Nautilus Trader
```

### Future Direct WebSocket Architecture
```
4OTC WebSocket → Direct Nautilus 4OTC Adapter → Nautilus Trader
                ↓
         (Optional NATS Publishing for other consumers)
```

## Implementation Plan

### Phase 1: Direct WebSocket Client

#### New Components to Add

1. **WebSocket Client Module** (`src/websocket/mod.rs`)
   - Connection management
   - Authentication handling
   - Message framing
   - Reconnection logic

2. **SBE Decoder Integration** (`src/websocket/decoder.rs`)
   - Direct integration with `four_otc_markets_market_data` decoder
   - Message parsing and validation
   - Error handling for malformed messages

3. **Configuration Extensions** (`src/config.rs`)
   - WebSocket connection parameters
   - Authentication credentials
   - Subscription management
   - Fallback modes

#### WebSocket Client Implementation

```rust
// src/websocket/client.rs
pub struct FourOtcWebSocketClient {
    config: WebSocketConfig,
    connection: Option<WebSocketStream>,
    decoder: SbeDecoder,
    data_sender: mpsc::UnboundedSender<Data>,
    subscriptions: Arc<RwLock<HashMap<u32, SubscriptionState>>>,
    stats: Arc<RwLock<WebSocketStats>>,
}

impl FourOtcWebSocketClient {
    pub async fn connect(&mut self) -> Result<()> {
        // Establish WebSocket connection
        // Handle authentication
        // Setup message processing
    }
    
    pub async fn subscribe_security(&mut self, security_id: u32) -> Result<()> {
        // Send subscription request
        // Track subscription state
    }
    
    async fn process_message(&self, data: &[u8]) -> Result<()> {
        // Decode SBE message
        // Convert to Nautilus data types
        // Send to data engine
    }
}
```

#### Configuration Extensions

```rust
// src/config.rs additions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WebSocketConfig {
    /// WebSocket URL
    pub url: String,
    
    /// Authentication token
    pub auth_token: Option<String>,
    
    /// Connection timeout
    pub connection_timeout_secs: u64,
    
    /// Heartbeat interval
    pub heartbeat_interval_secs: u64,
    
    /// Maximum reconnection attempts
    pub max_reconnect_attempts: u32,
    
    /// Reconnection delay strategy
    pub reconnect_delay_strategy: ReconnectStrategy,
    
    /// Enable message compression
    pub enable_compression: bool,
    
    /// Buffer size for incoming messages
    pub message_buffer_size: usize,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ReconnectStrategy {
    Fixed(u64),           // Fixed delay in milliseconds
    Exponential(u64, u64), // Initial delay, max delay
    Linear(u64),          // Linear backoff
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ConnectionMode {
    /// NATS-only mode (current)
    NatsOnly,
    
    /// WebSocket-only mode (direct)
    WebSocketOnly,
    
    /// Hybrid mode (WebSocket primary, NATS fallback)
    Hybrid {
        primary: PrimaryConnection,
        fallback_delay_ms: u64,
    },
    
    /// Dual mode (both connections active)
    Dual {
        websocket_priority: bool,
    },
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum PrimaryConnection {
    WebSocket,
    Nats,
}
```

### Phase 2: Hybrid Architecture

#### Connection Manager

```rust
// src/connection/manager.rs
pub struct ConnectionManager {
    config: FourOtcDataClientConfig,
    websocket_client: Option<FourOtcWebSocketClient>,
    nats_client: Option<NatsClient>,
    active_mode: ConnectionMode,
    failover_handler: FailoverHandler,
}

impl ConnectionManager {
    pub async fn start(&mut self) -> Result<()> {
        match self.config.connection_mode {
            ConnectionMode::WebSocketOnly => {
                self.start_websocket_only().await
            }
            ConnectionMode::NatsOnly => {
                self.start_nats_only().await
            }
            ConnectionMode::Hybrid { .. } => {
                self.start_hybrid_mode().await
            }
            ConnectionMode::Dual { .. } => {
                self.start_dual_mode().await
            }
        }
    }
    
    async fn handle_websocket_failure(&mut self) -> Result<()> {
        if matches!(self.config.connection_mode, ConnectionMode::Hybrid { .. }) {
            info!("WebSocket failed, falling back to NATS");
            self.start_nats_fallback().await
        } else {
            self.attempt_websocket_reconnection().await
        }
    }
}
```

#### Failover Logic

```rust
// src/connection/failover.rs
pub struct FailoverHandler {
    primary_failures: u32,
    last_failover: Option<Instant>,
    failover_cooldown: Duration,
}

impl FailoverHandler {
    pub fn should_failover(&self, failure_count: u32) -> bool {
        // Implement failover decision logic
        // Consider failure rate, cooldown period, etc.
    }
    
    pub async fn execute_failover(&mut self, 
        from: ConnectionType, 
        to: ConnectionType
    ) -> Result<()> {
        // Implement seamless failover
        // Ensure no data loss during transition
    }
}
```

### Phase 3: Performance Optimizations

#### Zero-Copy Processing

```rust
// src/performance/zero_copy.rs
pub struct ZeroCopyProcessor {
    buffer_pool: BufferPool,
    decoder: SbeDecoder,
}

impl ZeroCopyProcessor {
    pub fn process_message_zerocopy(&mut self, data: &[u8]) -> Result<DataRef> {
        // Process without copying data
        // Return references to original buffer
        // Implement buffer lifecycle management
    }
}
```

#### SIMD Optimizations

```rust
// src/performance/simd.rs
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

pub fn fast_price_conversion(raw_prices: &[u64]) -> Vec<Price> {
    // Use SIMD instructions for bulk price conversions
    // Optimize for common price precision patterns
}
```

#### Lock-Free Data Structures

```rust
// src/performance/lockfree.rs
use crossbeam::queue::ArrayQueue;
use std::sync::atomic::{AtomicPtr, Ordering};

pub struct LockFreeMessageQueue {
    queue: ArrayQueue<MessageBox>,
    stats: AtomicStats,
}

impl LockFreeMessageQueue {
    pub fn push(&self, message: Message) -> Result<(), Message> {
        // Lock-free message queuing
        // High-performance producer-consumer pattern
    }
}
```

## Technical Specifications

### WebSocket Protocol Details

#### Connection Establishment
1. **Handshake**: Standard WebSocket handshake with custom headers
2. **Authentication**: Token-based or certificate-based authentication
3. **Protocol Selection**: Negotiate message format (binary SBE)
4. **Compression**: Optional message compression (deflate/gzip)

#### Message Framing
```
+--------+--------+--------+--------+
| Length |  Type  |    Sequence     |
+--------+--------+--------+--------+
|        Message Payload             |
|               ...                  |
+------------------------------------+
```

#### Subscription Management
```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SubscriptionRequest {
    pub request_id: String,
    pub security_ids: Vec<u32>,
    pub venue_ids: Vec<u32>,
    pub data_types: Vec<DataType>,
    pub market_depth: Option<u32>,
}

#[derive(Debug, Clone)]
pub enum DataType {
    Trades,
    OrderBookSnapshot,
    OrderBookUpdates,
    SecurityDefinitions,
    SecurityStatus,
}
```

### Performance Targets

| Metric | NATS Mode | WebSocket Mode | Improvement |
|--------|-----------|----------------|-------------|
| Latency (p99) | 500μs | 100μs | 5x |
| Throughput | 100k msg/s | 500k msg/s | 5x |
| Memory Usage | 100MB | 50MB | 2x |
| CPU Usage | 20% | 10% | 2x |

### Reliability Features

#### Heartbeat Mechanism
```rust
#[derive(Debug, Clone)]
pub struct HeartbeatConfig {
    pub interval_ms: u64,
    pub timeout_ms: u64,
    pub max_missed: u32,
}

impl HeartbeatMonitor {
    pub async fn monitor(&self) -> Result<()> {
        // Send periodic heartbeats
        // Monitor server responses
        // Trigger reconnection on timeout
    }
}
```

#### Message Sequencing
```rust
pub struct SequenceTracker {
    expected_sequence: AtomicU64,
    gaps: RwLock<BTreeSet<u64>>,
    gap_requests: RwLock<HashMap<u64, Instant>>,
}

impl SequenceTracker {
    pub fn check_sequence(&self, seq: u64) -> SequenceResult {
        // Detect missing messages
        // Request gap fills
        // Handle duplicate messages
    }
}
```

## Migration Strategy

### Phase 1: NATS-Only (Current)
- ✅ Complete NATS-based integration
- ✅ Full feature parity with requirements
- ✅ Production-ready implementation

### Phase 2: Hybrid Implementation
- 🔄 Add WebSocket client alongside NATS
- 🔄 Implement seamless failover
- 🔄 Performance benchmarking

### Phase 3: WebSocket-Primary
- ⏳ Make WebSocket the primary connection
- ⏳ NATS as backup/fallback
- ⏳ Advanced performance optimizations

### Phase 4: WebSocket-Only (Optional)
- ⏳ Remove NATS dependency (optional)
- ⏳ Pure WebSocket implementation
- ⏳ Maximum performance mode

## Testing Strategy

### Unit Tests
```rust
#[tokio::test]
async fn test_websocket_connection() {
    let config = WebSocketConfig::test_config();
    let mut client = FourOtcWebSocketClient::new(config);
    
    assert!(client.connect().await.is_ok());
    assert_eq!(client.state(), ConnectionState::Connected);
}

#[tokio::test]
async fn test_message_processing() {
    let test_data = include_bytes!("test_data/sbe_message.bin");
    let result = process_sbe_message(test_data).await;
    
    assert!(result.is_ok());
    let data = result.unwrap();
    assert_eq!(data.instrument_id().symbol.as_str(), "BTCUSD");
}
```

### Integration Tests
```rust
#[tokio::test]
async fn test_failover_scenario() {
    let config = hybrid_test_config();
    let mut manager = ConnectionManager::new(config);
    
    // Start with WebSocket
    manager.start().await.unwrap();
    assert_eq!(manager.active_connection(), ConnectionType::WebSocket);
    
    // Simulate WebSocket failure
    manager.simulate_websocket_failure().await;
    
    // Should failover to NATS
    assert_eq!(manager.active_connection(), ConnectionType::Nats);
}
```

### Performance Tests
```rust
#[tokio::test]
async fn benchmark_message_throughput() {
    let start = Instant::now();
    let message_count = 1_000_000;
    
    for _ in 0..message_count {
        process_test_message().await;
    }
    
    let elapsed = start.elapsed();
    let throughput = message_count as f64 / elapsed.as_secs_f64();
    
    println!("Throughput: {:.0} messages/second", throughput);
    assert!(throughput > 100_000.0); // Minimum 100k msg/s
}
```

## Risk Assessment

### Technical Risks
1. **WebSocket Stability**: 4OTC WebSocket API stability and changes
2. **Message Ordering**: Ensuring correct message sequence in high-throughput scenarios
3. **Memory Management**: Preventing memory leaks in long-running connections
4. **Error Recovery**: Robust error handling and recovery mechanisms

### Mitigation Strategies
1. **Extensive Testing**: Comprehensive test suite with edge cases
2. **Monitoring**: Real-time monitoring of connection health and performance
3. **Fallback Mechanisms**: NATS fallback for WebSocket failures
4. **Circuit Breakers**: Prevent cascading failures

## Timeline

### Month 1: Foundation
- [ ] WebSocket client implementation
- [ ] Basic SBE message processing
- [ ] Unit test coverage

### Month 2: Integration
- [ ] Hybrid mode implementation
- [ ] Failover mechanisms
- [ ] Integration testing

### Month 3: Optimization
- [ ] Performance optimizations
- [ ] Production deployment
- [ ] Documentation and training

## Success Metrics

### Performance Metrics
- **Latency**: < 100μs p99 for WebSocket mode
- **Throughput**: > 500k messages/second
- **Reliability**: 99.99% uptime
- **Resource Usage**: < 50MB memory, < 10% CPU

### Quality Metrics
- **Test Coverage**: > 90%
- **Code Quality**: No critical issues in static analysis
- **Documentation**: Complete API and user documentation
- **Performance**: All benchmarks passing

## Future Enhancements

### Advanced Features
1. **Message Compression**: Reduce bandwidth usage
2. **Parallel Processing**: Multi-threaded message processing
3. **Smart Routing**: Intelligent connection selection
4. **Adaptive Buffering**: Dynamic buffer size adjustment

### Monitoring and Observability
1. **Metrics Export**: Prometheus metrics integration
2. **Distributed Tracing**: OpenTelemetry support
3. **Health Checks**: Comprehensive health monitoring
4. **Alerting**: Automated alerting on anomalies

## Conclusion

The direct WebSocket integration plan provides a clear path to ultra-low latency market data access while maintaining the robustness and reliability of the current NATS-based implementation. The phased approach ensures minimal risk and allows for gradual migration and optimization.

The implementation will follow Nautilus Trader's architectural principles and maintain compatibility with existing strategies and systems while providing significant performance improvements for latency-sensitive applications.