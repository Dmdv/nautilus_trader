# Configuration Guide

This guide covers configuring NautilusTrader for multi-exchange crypto trading.

---

## Quick Start

```bash
# 1. Generate configuration template
make config-template

# 2. Copy and edit
cp .env.template .env

# 3. Verify configuration
make config-check

# 4. Test exchange connectivity
make exchange-status
```

---

## Exchange Configuration

### Supported Exchanges

| Exchange | Spot | Futures | Adapter Status |
|----------|------|---------|----------------|
| Binance | ✅ | ✅ | Stable |
| Bybit | ✅ | ✅ | Stable |
| OKX | ✅ | ✅ | Stable |
| dYdX | - | ✅ | Stable |

---

## Binance Configuration

### Environment Variables

```bash
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
BINANCE_TESTNET=true  # Set to false for mainnet
```

### Client Configuration

```python
from nautilus_trader.adapters.binance.config import (
    BinanceDataClientConfig,
    BinanceExecClientConfig,
)
from nautilus_trader.adapters.binance.common.enums import BinanceAccountType

# Data client (market data feed)
data_config = BinanceDataClientConfig(
    api_key=os.environ["BINANCE_API_KEY"],
    api_secret=os.environ["BINANCE_API_SECRET"],
    account_type=BinanceAccountType.USDT_FUTURE,  # or SPOT, COIN_FUTURE
    testnet=True,

    # Rate limiting
    rate_limit_per_second=10,

    # Data options
    use_agg_trade_ticks=True,  # Aggregated trades (recommended)
)

# Execution client (order management)
exec_config = BinanceExecClientConfig(
    api_key=os.environ["BINANCE_API_KEY"],
    api_secret=os.environ["BINANCE_API_SECRET"],
    account_type=BinanceAccountType.USDT_FUTURE,
    testnet=True,

    # Position mode
    use_position_ids=True,  # Track positions by ID
)
```

### Account Types

| Type | Description | Use Case |
|------|-------------|----------|
| `SPOT` | Spot trading | Buy/sell crypto directly |
| `MARGIN` | Cross/isolated margin | Leveraged spot trading |
| `USDT_FUTURE` | USDT-margined perpetuals | Most common for futures |
| `COIN_FUTURE` | Coin-margined perpetuals | Inverse contracts |

### Position Modes

```python
# One-way mode (default)
# Single position per symbol - simpler but less flexible
position_mode = "one_way"

# Hedge mode
# Separate long/short positions - better for complex strategies
position_mode = "hedge"
```

### Rate Limits

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Orders | 10/sec | Per second |
| Request weight | 1200 | Per minute |
| Raw requests | 5000 | Per 5 minutes |

---

## Bybit Configuration

### Environment Variables

```bash
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
BYBIT_TESTNET=true
```

### Client Configuration

```python
from nautilus_trader.adapters.bybit.config import (
    BybitDataClientConfig,
    BybitExecClientConfig,
)
from nautilus_trader.adapters.bybit.common.enums import BybitAccountType

# Data client
data_config = BybitDataClientConfig(
    api_key=os.environ["BYBIT_API_KEY"],
    api_secret=os.environ["BYBIT_API_SECRET"],
    account_type=BybitAccountType.UNIFIED,  # or CONTRACT
    testnet=True,
)

# Execution client
exec_config = BybitExecClientConfig(
    api_key=os.environ["BYBIT_API_KEY"],
    api_secret=os.environ["BYBIT_API_SECRET"],
    account_type=BybitAccountType.UNIFIED,
    testnet=True,
)
```

### Account Types

| Type | Description | Use Case |
|------|-------------|----------|
| `UNIFIED` | Unified trading account | Recommended - single account for all products |
| `CONTRACT` | Legacy contract account | Older perpetual contracts |

### Rate Limits

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Orders | 50/sec | Per second |
| General | 120 | Per 5 seconds |

---

## OKX Configuration

### Environment Variables

```bash
OKX_API_KEY=your_api_key
OKX_API_SECRET=your_api_secret
OKX_PASSPHRASE=your_passphrase  # Required for OKX
OKX_TESTNET=true
```

### Client Configuration

```python
from nautilus_trader.adapters.okx.config import (
    OKXDataClientConfig,
    OKXExecClientConfig,
)
from nautilus_trader.adapters.okx.common.enums import OKXAccountType

# Data client
data_config = OKXDataClientConfig(
    api_key=os.environ["OKX_API_KEY"],
    api_secret=os.environ["OKX_API_SECRET"],
    passphrase=os.environ["OKX_PASSPHRASE"],
    account_type=OKXAccountType.UNIFIED,
    is_demo=True,  # Testnet
)

# Execution client
exec_config = OKXExecClientConfig(
    api_key=os.environ["OKX_API_KEY"],
    api_secret=os.environ["OKX_API_SECRET"],
    passphrase=os.environ["OKX_PASSPHRASE"],
    account_type=OKXAccountType.UNIFIED,
    is_demo=True,
)
```

### Account Types

| Type | Description | Position Mode |
|------|-------------|---------------|
| `UNIFIED` | Unified account | Net position |
| `PORTFOLIO_MARGIN` | Portfolio margin | Net position |

### Rate Limits

| Endpoint Type | Limit | Window |
|---------------|-------|--------|
| Orders | 60/sec | Per second |
| General | 300 | Per 2 seconds |

---

## dYdX Configuration

⚠️ **Security Note**: dYdX uses wallet-based authentication. See [SECURITY.md](SECURITY.md) for mnemonic handling.

### Environment Variables

```bash
# TESTNET ONLY - Use hardware wallet for mainnet
DYDX_MNEMONIC=word1 word2 ... word24
DYDX_NETWORK=testnet  # or mainnet
```

### Client Configuration

```python
from nautilus_trader.adapters.dydx.config import (
    DYDXDataClientConfig,
    DYDXExecClientConfig,
)

# Data client
data_config = DYDXDataClientConfig(
    wallet_address="your_wallet_address",
    is_testnet=True,
)

# Execution client
exec_config = DYDXExecClientConfig(
    wallet_address="your_wallet_address",
    mnemonic=os.environ["DYDX_MNEMONIC"],  # Only for testnet!
    is_testnet=True,

    # dYdX-specific
    subaccount_number=0,  # Default subaccount
)
```

### Network Endpoints

| Network | Indexer | Validator |
|---------|---------|-----------|
| Testnet | `https://indexer.v4testnet.dydx.exchange` | `https://test-dydx.kingnodes.com` |
| Mainnet | `https://indexer.dydx.trade` | `https://dydx-mainnet.kingnodes.com` |

### Rate Limits

dYdX uses L2 (Cosmos) for execution:
- No traditional rate limits
- Gas-based transaction costs
- ~5 orders/second recommended

---

## Node Configuration

### TradingNode Configuration

```python
from nautilus_trader.config import (
    TradingNodeConfig,
    CacheDatabaseConfig,
    LiveDataEngineConfig,
    LiveExecEngineConfig,
)

config = TradingNodeConfig(
    # Identification
    trader_id="TRADER-001",
    instance_id="INSTANCE-001",

    # Logging
    log_level="INFO",           # DEBUG, INFO, WARNING, ERROR
    log_level_file="DEBUG",     # File logging level
    log_file_path="logs/",      # Log directory
    log_component_levels={      # Per-component levels
        "DataEngine": "INFO",
        "ExecEngine": "DEBUG",
    },

    # Cache (Redis for production)
    cache_database=CacheDatabaseConfig(
        type="redis",
        host="localhost",
        port=6379,
        db=0,
    ),

    # Timeouts
    timeout_connection=30.0,        # Connection timeout (seconds)
    timeout_reconciliation=60.0,    # Position reconciliation timeout
    timeout_portfolio=10.0,         # Portfolio calculation timeout
    timeout_disconnection=5.0,      # Graceful disconnect timeout

    # Data engine
    data_engine=LiveDataEngineConfig(
        time_bars_build_with_no_updates=True,
        time_bars_timestamp_on_close=True,
        validate_data_sequence=True,
    ),

    # Execution engine
    exec_engine=LiveExecEngineConfig(
        reconciliation=True,              # Always True for production
        reconciliation_lookback_mins=1440, # 24 hours lookback
        filter_unclaimed_external_orders=True,
        filter_position_reports=False,
    ),
)
```

### Exchange-Specific Timeouts

| Exchange | Connection | Reconciliation | Notes |
|----------|------------|----------------|-------|
| Binance | 10s | 30s | Fast REST API |
| Bybit | 10s | 30s | Fast REST API |
| OKX | 10s | 30s | Fast REST API |
| dYdX | 30s | 60s | L2 settlement delays |

---

## Redis Configuration

Redis provides state persistence and recovery for production systems.

### Installation

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### Recommended Configuration

Create `/etc/redis/redis.conf` or edit existing:

```conf
# Memory management
maxmemory 2gb
maxmemory-policy allkeys-lru

# Persistence
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Performance
tcp-keepalive 300
timeout 0

# Security (production)
# requirepass your_secure_password
# bind 127.0.0.1
```

### Connection Configuration

```python
cache_database=CacheDatabaseConfig(
    type="redis",
    host="localhost",
    port=6379,
    db=0,
    # password="your_secure_password",  # For production
    # ssl=True,  # For remote Redis
)
```

### Health Check

```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Check memory usage
redis-cli info memory | grep used_memory_human
```

---

## Logging Configuration

### Log Levels

| Level | Use Case |
|-------|----------|
| `DEBUG` | Development, troubleshooting |
| `INFO` | Production default |
| `WARNING` | Important alerts only |
| `ERROR` | Errors only |

### Component-Level Logging

```python
log_component_levels={
    "DataEngine": "INFO",      # Market data flow
    "ExecEngine": "DEBUG",     # Order execution (verbose)
    "RiskEngine": "WARNING",   # Risk checks
    "Portfolio": "INFO",       # Position updates
    "Strategy": "DEBUG",       # Strategy logic
}
```

### Log Output

Logs are written to:
- Console (stdout) - configurable level
- File (`logs/nautilus_<timestamp>.log`) - typically more verbose

### Log Rotation

For production, use logrotate:

```conf
# /etc/logrotate.d/nautilus
/path/to/logs/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 nautilus nautilus
}
```

---

## Multi-Venue Setup

### Adding Multiple Exchanges

```python
from nautilus_trader.live.node import TradingNode

# Create node
node = TradingNode(config=trading_node_config)

# Add Binance
node.add_data_client(binance_data_config)
node.add_exec_client(binance_exec_config)

# Add Bybit
node.add_data_client(bybit_data_config)
node.add_exec_client(bybit_exec_config)

# Add OKX
node.add_data_client(okx_data_config)
node.add_exec_client(okx_exec_config)

# Add dYdX
node.add_data_client(dydx_data_config)
node.add_exec_client(dydx_exec_config)

# Add strategy (can trade on any venue)
node.add_strategy(my_strategy)

# Run
node.run()
```

### Cross-Venue Order Routing

```python
# In your strategy
def on_signal(self, signal):
    # Route to best venue based on spread/liquidity
    best_venue = self.find_best_venue(signal.instrument_id)

    order = self.order_factory.market(
        instrument_id=signal.instrument_id,
        order_side=signal.side,
        quantity=signal.quantity,
    )

    self.submit_order(order)  # Routes to correct venue automatically
```

---

## Configuration Validation

### Verify Configuration

```bash
# Check all config values
make config-check

# Test exchange connectivity
make exchange-status

# Test API credentials (read-only)
make credentials-test
```

### Common Issues

**API Key Invalid**
```
Error: Invalid API key
Solution: Verify key in exchange dashboard, check for extra whitespace
```

**IP Not Whitelisted**
```
Error: IP address not in whitelist
Solution: Add server IP to exchange API settings (see SECURITY.md)
```

**Testnet/Mainnet Mismatch**
```
Error: Invalid endpoint
Solution: Ensure testnet flag matches your API key type
```

**Rate Limit Exceeded**
```
Error: Too many requests
Solution: Reduce request frequency, check rate_limit_per_second setting
```

---

## Environment-Specific Configurations

### Development

```python
config = TradingNodeConfig(
    trader_id="DEV-001",
    log_level="DEBUG",
    log_level_file="DEBUG",
    cache_database=None,  # In-memory only
    timeout_connection=10.0,
)
```

### Paper Trading (Testnet)

```python
config = TradingNodeConfig(
    trader_id="PAPER-001",
    log_level="INFO",
    log_level_file="DEBUG",
    cache_database=CacheDatabaseConfig(type="redis", host="localhost"),
    exec_engine=LiveExecEngineConfig(reconciliation=True),
)

# Use testnet endpoints
binance_config = BinanceDataClientConfig(testnet=True)
```

### Production

```python
config = TradingNodeConfig(
    trader_id="PROD-001",
    log_level="INFO",
    log_level_file="INFO",  # Less verbose for production
    cache_database=CacheDatabaseConfig(
        type="redis",
        host="redis.internal",
        port=6379,
        password=os.environ["REDIS_PASSWORD"],
    ),
    exec_engine=LiveExecEngineConfig(
        reconciliation=True,
        reconciliation_lookback_mins=1440,
    ),
)

# Use mainnet endpoints
binance_config = BinanceDataClientConfig(testnet=False)
```

---

## Next Steps

1. **Set up data pipeline**: [DATA_INGESTION.md](DATA_INGESTION.md)
2. **Build your strategy**: [STRATEGY_DEVELOPMENT.md](STRATEGY_DEVELOPMENT.md)
3. **Run backtests**: [BACKTESTING.md](BACKTESTING.md)
