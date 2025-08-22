# 4OTC Integration

This page describes how to integrate [4OTC](https://4otc.com) market data with Nautilus Trader using the dedicated 4OTC adapter.

## Overview

The 4OTC adapter provides real-time market data integration through a NATS-based messaging architecture. This design offers:

- **High Performance**: Low-latency market data delivery
- **Scalability**: Horizontal scaling through NATS messaging
- **Reliability**: Message persistence and replay capabilities
- **Flexibility**: Support for multiple data formats and subscription patterns

## Architecture

The integration consists of two main components:

1. **4OTC Market Data Adapter**: Connects to 4OTC WebSocket feeds, decodes SBE messages, and publishes to NATS
2. **Nautilus 4OTC Adapter**: Consumes NATS messages and converts them to Nautilus data types

```mermaid
graph LR
    A[4OTC WebSocket] --> B[Market Data Adapter]
    B --> C[NATS Message Broker]
    C --> D[Nautilus 4OTC Adapter]
    D --> E[Nautilus Trader]
    
    B --> F[SBE Decoder]
    F --> G[Message Publisher]
    G --> C
    
    D --> H[Data Converter]
    H --> I[Nautilus Data Types]
    I --> E
```

## Prerequisites

- **Rust**: Version 1.89.0 or later
- **NATS Server**: Running locally or remotely
- **4OTC Access**: Valid credentials and market data access
- **Market Data Adapter**: The 4OTC market data adapter must be running

## Installation

### From Source

Clone and build the 4OTC adapter:

```bash
git clone https://github.com/nautechsystems/nautilus_trader.git
cd nautilus_trader
cargo build -p fourotc
```

### Python Installation

The adapter will be available through PyPI in future releases:

```bash
# Future release
pip install nautilus-trader[fourotc]
```

## Configuration

### Basic Configuration

Create a configuration for the 4OTC data client:

```python
from nautilus_trader.adapters.fourotc import FourOtcDataClientConfig
from nautilus_trader.model.identifiers import ClientId, Venue

# Basic configuration
config = FourOtcDataClientConfig(
    client_id=ClientId("FOUROTC-001"),
    venue=Venue("4OTC"),
    nats_servers=["nats://localhost:4222"],
    debug_mode=False
)
```

### Advanced Configuration

```python
from nautilus_trader.adapters.fourotc import (
    FourOtcDataClientConfig,
    NatsConfig,
    DataFormat
)

# Create NATS configuration
nats_config = NatsConfig(
    servers=["nats://server1:4222", "nats://server2:4222"],
    subject_prefix="market.4otc",
    client_name="nautilus-client",
    connection_timeout_secs=10,
    enable_jetstream=True
)

# Create advanced configuration
config = FourOtcDataClientConfig(
    client_id=ClientId("FOUROTC-PROD"),
    venue=Venue("4OTC"),
    nats=nats_config,
    data_format=DataFormat.PROTOBUF,
    buffer_size=100000,
    enable_message_filtering=True
)
```

### Environment-Specific Configurations

```python
# Development configuration
dev_config = FourOtcDataClientConfig.development()
dev_config.debug_mode = True

# Production configuration
prod_config = FourOtcDataClientConfig.production()
prod_config.nats.servers = [
    "nats://prod-nats-1:4222",
    "nats://prod-nats-2:4222",
    "nats://prod-nats-3:4222"
]
```

## Usage

### Live Trading Node

```python
from nautilus_trader.live.node import TradingNode
from nautilus_trader.adapters.fourotc import FourOtcDataClientFactory
from nautilus_trader.config import TradingNodeConfig

# Create trading node configuration
node_config = TradingNodeConfig(
    trader_id="TRADER-001",
    data_clients={
        "FOUROTC": {
            "factory": FourOtcDataClientFactory,
            "config": {
                "client_id": "FOUROTC-001",
                "venue": "4OTC",
                "nats_servers": ["nats://localhost:4222"],
                "subscriptions": {
                    "trades": True,
                    "order_book_snapshots": True,
                    "order_book_updates": True,
                    "security_definitions": True
                }
            }
        }
    }
)

# Create and start trading node
node = TradingNode(config=node_config)
node.start()
```

### Data Engine Integration

```python
from nautilus_trader.live.data_engine import LiveDataEngine
from nautilus_trader.adapters.fourotc import FourOtcDataClient
from nautilus_trader.model.identifiers import InstrumentId

# Create data client
client = FourOtcDataClient(config=config)

# Create data engine
data_engine = LiveDataEngine(
    loop=asyncio.get_event_loop(),
    msgbus=message_bus,
    cache=cache,
    clock=clock,
    logger=logger
)

# Register client
data_engine.register_client(client)

# Subscribe to instruments
instruments = [
    InstrumentId.from_str("BTCUSD.4OTC"),
    InstrumentId.from_str("ETHUSD.4OTC"),
]

for instrument_id in instruments:
    # Subscribe to trades
    data_engine.subscribe_trade_ticks(instrument_id)
    
    # Subscribe to order book
    data_engine.subscribe_order_book_depth10(instrument_id)
    
    # Subscribe to quotes
    data_engine.subscribe_quote_ticks(instrument_id)
```

### Strategy Integration

```python
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.data import TradeTick, OrderBookDepth10

class FourOtcStrategy(Strategy):
    def on_start(self):
        # Subscribe to 4OTC instruments
        self.subscribe_trade_ticks(InstrumentId.from_str("BTCUSD.4OTC"))
        self.subscribe_order_book_depth10(InstrumentId.from_str("BTCUSD.4OTC"))
    
    def on_trade_tick(self, tick: TradeTick):
        # Handle trade data from 4OTC
        self.log.info(f"4OTC Trade: {tick}")
    
    def on_order_book_depth10(self, depth: OrderBookDepth10):
        # Handle order book data from 4OTC
        best_bid = depth.bids[0].price if depth.bids else None
        best_ask = depth.asks[0].price if depth.asks else None
        self.log.info(f"4OTC Book: {best_bid} x {best_ask}")
```

## Instrument Setup

### Security ID Mapping

4OTC uses numeric security IDs that must be mapped to Nautilus instrument identifiers:

```python
# Register instrument mappings
client.register_instrument(
    security_id=100,  # 4OTC security ID
    instrument_id=InstrumentId.from_str("BTCUSD.4OTC")
)

client.register_instrument(
    security_id=101,  # 4OTC security ID  
    instrument_id=InstrumentId.from_str("ETHUSD.4OTC")
)
```

### Instrument Factory

```python
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Price, Quantity

def create_fourotc_instrument(security_id: int, symbol: str) -> CurrencyPair:
    return CurrencyPair(
        instrument_id=InstrumentId.from_str(f"{symbol}.4OTC"),
        symbol=Symbol(symbol),
        base_currency=Currency.from_str(symbol[:3]),
        quote_currency=Currency.from_str(symbol[3:]),
        price_precision=8,
        size_precision=8,
        tick_size=Price("0.00000001"),
        lot_size=Quantity("0.00000001"),
        ts_event=0,
        ts_init=0
    )

# Create and register instruments
btc_usd = create_fourotc_instrument(100, "BTCUSD")
eth_usd = create_fourotc_instrument(101, "ETHUSD")
```

## Market Data Types

### Available Data

| Data Type | Description | Nautilus Type |
|-----------|-------------|---------------|
| Trades | Individual trade executions | `TradeTick` |
| Order Books | Level 2 snapshots and updates | `OrderBookDepth10` |
| Quotes | Best bid/ask prices | `QuoteTick` |
| Security Definitions | Instrument metadata | Custom handling |
| Security Status | Trading status updates | `InstrumentStatus` |

### Subscription Examples

```python
# Subscribe to all data types for an instrument
instrument_id = InstrumentId.from_str("BTCUSD.4OTC")

# Trade data
client.subscribe_trade_ticks(instrument_id)

# Order book depth
client.subscribe_order_book_depth10(instrument_id)

# Quote ticks (derived from order book)
client.subscribe_quote_ticks(instrument_id)

# Order book deltas (if supported)
client.subscribe_order_book_deltas(instrument_id)
```

## NATS Integration

### Subject Structure

The adapter uses hierarchical NATS subjects:

```
market.4otc.
├── heartbeat                           # System heartbeats
├── trades.<venue_id>                   # Trade executions  
├── snapshot.level2.<venue_id>.<sec_id> # Order book snapshots
├── security.definition.<sec_id>        # Security definitions
├── security.status.<sec_id>            # Security status
└── request.{accept|reject}.<req_id>    # Request responses
```

### Manual NATS Subscription

For advanced use cases, you can subscribe directly to NATS:

```python
import asyncio
import nats

async def message_handler(msg):
    subject = msg.subject
    data = msg.data
    print(f"Received on {subject}: {data}")

async def main():
    nc = await nats.connect("nats://localhost:4222")
    
    # Subscribe to all 4OTC trades
    await nc.subscribe("market.4otc.trades.*", cb=message_handler)
    
    # Subscribe to specific order book
    await nc.subscribe("market.4otc.snapshot.level2.1.100", cb=message_handler)
    
    # Keep alive
    await asyncio.sleep(60)
    await nc.close()

asyncio.run(main())
```

## Performance Optimization

### High-Frequency Trading

For high-frequency scenarios:

```python
config = FourOtcDataClientConfig.production()

# Optimize for performance
config.buffer_size = 1000000  # Large buffer
config.data_format = DataFormat.PROTOBUF  # Faster serialization
config.enable_message_filtering = True  # Filter unnecessary messages
config.heartbeat_interval_secs = 5  # Faster health checks

# Use multiple NATS connections
config.nats.pool_size = 4
```

### Memory Management

```python
# Monitor memory usage
import psutil
import gc

def monitor_memory():
    process = psutil.Process()
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"Memory usage: {memory_mb:.1f} MB")
    
    # Force garbage collection if needed
    if memory_mb > 1000:  # 1GB threshold
        gc.collect()

# Schedule periodic monitoring
import schedule
schedule.every(30).seconds.do(monitor_memory)
```

## Monitoring and Alerting

### Statistics Monitoring

```python
import time
from datetime import datetime, timedelta

async def monitor_statistics():
    while True:
        stats = await client.get_stats()
        
        # Log statistics
        print(f"Messages: {stats.messages_received}")
        print(f"Success rate: {stats.success_rate():.2%}")
        print(f"Error rate: {stats.error_rate():.2%}")
        
        # Alert on high error rates
        if stats.error_rate() > 0.1:  # 10% threshold
            print("⚠️ High error rate detected!")
            # Send alert to monitoring system
        
        await asyncio.sleep(30)

# Start monitoring
asyncio.create_task(monitor_statistics())
```

### Health Checks

```python
async def health_check():
    try:
        # Check connection state
        state = await client.get_connection_state()
        if state != ConnectionState.CONNECTED:
            raise Exception(f"Client not connected: {state}")
        
        # Check recent message activity
        stats = await client.get_stats()
        if stats.last_message_time:
            last_msg_age = time.time() - stats.last_message_time / 1e9
            if last_msg_age > 60:  # No messages for 1 minute
                raise Exception(f"No recent messages: {last_msg_age:.1f}s ago")
        
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

# Periodic health checks
async def health_monitor():
    while True:
        healthy = await health_check()
        if not healthy:
            # Attempt reconnection
            await client.disconnect()
            await asyncio.sleep(5)
            await client.connect()
        
        await asyncio.sleep(30)
```

## Troubleshooting

### Common Issues

#### Connection Problems

**Problem**: `NATS connection failed: no servers available`
```python
# Solution: Check NATS server and configuration
config.nats.servers = ["nats://localhost:4222"]
config.nats.connection_timeout_secs = 30  # Increase timeout
```

**Problem**: `Authentication failed`
```python
# Solution: Configure NATS authentication
config.nats.auth_token = "your-auth-token"
# or
config.nats.user = "username"
config.nats.password = "password"
```

#### Message Processing Issues

**Problem**: `Message parsing error: Invalid JSON`
```python
# Solution: Check data format configuration
config.data_format = DataFormat.JSON  # or DataFormat.PROTOBUF
```

**Problem**: `High memory usage`
```python
# Solution: Reduce buffer size and enable filtering
config.buffer_size = 10000
config.enable_message_filtering = True
```

#### Performance Issues

**Problem**: `Missing messages or delays`
```python
# Solution: Optimize configuration
config.buffer_size = 100000
config.nats.max_pending_msgs = 1000000
config.nats.max_pending_bytes = 100 * 1024 * 1024  # 100MB
```

### Debug Mode

Enable debug logging:

```python
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("fourotc")

# Enable debug mode
config.debug_mode = True
```

### Message Tracing

Trace message flow:

```python
class MessageTracer:
    def __init__(self):
        self.message_count = 0
        self.start_time = time.time()
    
    def trace_message(self, data):
        self.message_count += 1
        if self.message_count % 1000 == 0:
            elapsed = time.time() - self.start_time
            rate = self.message_count / elapsed
            print(f"Processed {self.message_count} messages at {rate:.1f}/sec")

tracer = MessageTracer()

# Hook into data processing
def on_data(data):
    tracer.trace_message(data)
    # Process data normally
```

## Best Practices

### Production Deployment

1. **Use NATS Clusters**: Deploy NATS in cluster mode for high availability
2. **Enable JetStream**: Use JetStream for message persistence and replay
3. **Monitor Performance**: Implement comprehensive monitoring and alerting
4. **Security**: Use TLS and authentication for NATS connections
5. **Resource Limits**: Set appropriate memory and CPU limits

### Development

1. **Use Development Config**: Start with `FourOtcDataClientConfig.development()`
2. **Enable Debug Logging**: Use debug mode for detailed logging
3. **Test Locally**: Run NATS server locally for development
4. **Mock Data**: Use mock data for testing when 4OTC feeds are unavailable

### Testing

```python
import pytest
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_fourotc_client():
    # Mock configuration
    config = FourOtcDataClientConfig.development()
    
    # Create client
    client = FourOtcDataClient(config)
    
    # Mock NATS connection
    client.nats_client = AsyncMock()
    
    # Test connection
    await client.connect()
    assert await client.get_connection_state() == ConnectionState.CONNECTED
    
    # Test subscription
    instrument_id = InstrumentId.from_str("BTCUSD.4OTC")
    await client.subscribe_trade_ticks(instrument_id)
    
    # Cleanup
    await client.disconnect()
```

## API Reference

### Classes

- `FourOtcDataClient`: Main data client class
- `FourOtcDataClientConfig`: Configuration class
- `NatsConfig`: NATS-specific configuration
- `DataConverter`: Message conversion utilities

### Enums

- `ConnectionState`: Client connection states
- `MessageType`: 4OTC message types
- `DataFormat`: Serialization formats
- `TradingStatus`: Instrument trading status

For detailed API documentation, see the [API Reference](../api_reference/adapters/fourotc.md).

## Examples

Complete examples are available in the [repository](https://github.com/nautechsystems/nautilus_trader/tree/master/examples/live/fourotc).

## Support

- **GitHub Issues**: Report bugs and request features
- **Discord**: Join the Nautilus Trader community
- **Documentation**: Comprehensive guides and API reference
- **Examples**: Working code examples and tutorials

## See Also

- [Data Types](../concepts/data.md)
- [Live Trading](../concepts/live.md)
- [Adapters](../concepts/adapters.md)
- [NATS Documentation](https://docs.nats.io/)