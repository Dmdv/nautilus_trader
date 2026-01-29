# Deployment Guide

This guide covers the complete deployment progression from backtesting to production for NautilusTrader.

---

## Deployment Progression

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Backtest   │───▶│   Dry-Run   │───▶│   Shadow    │───▶│   Paper     │───▶│  Production │
│             │    │  (Sandbox)  │    │  (Parallel) │    │  (Testnet)  │    │  (Mainnet)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     │                   │                  │                  │                   │
     ▼                   ▼                  ▼                  ▼                   ▼
  Historical         Live Data          Live Data          Live Data           Live Data
  Simulation        No Orders          No Orders          Test Orders         Real Orders
```

### Stage Gates

| Stage | Entry Criteria | Exit Criteria |
|-------|----------------|---------------|
| Backtest | Strategy code complete | Sharpe > 1.5, WFE > 0.5, Monte Carlo p < 0.05 |
| Dry-Run | Backtest validated | 72h stable, no errors, latency < 100ms |
| Shadow | Dry-run validated | 7d tracking error < 2%, fill assumptions valid |
| Paper | Shadow validated | 14d profitable, drawdown < limits |
| Production | Paper validated | Risk committee approval, ops runbook complete |

---

## Stage 1: Dry-Run Mode

Dry-run executes strategy logic against live market data without submitting orders. Validates:
- Data pipeline stability
- Strategy signal generation
- Latency characteristics
- Memory/CPU usage

### Configuration

```python
from nautilus_trader.config import TradingNodeConfig, LiveExecEngineConfig

# Dry-run configuration - execution disabled
dry_run_config = TradingNodeConfig(
    trader_id="DRY-001",
    instance_id="DRY-RUN-001",

    log_level="DEBUG",
    log_level_file="DEBUG",
    log_file_path="logs/dry_run/",

    # No cache persistence for dry-run
    cache_database=None,

    # Execution engine - reconciliation disabled
    exec_engine=LiveExecEngineConfig(
        reconciliation=False,  # No position reconciliation
    ),
)
```

### Execution Client Configuration

```python
from nautilus_trader.adapters.binance.config import BinanceExecClientConfig
from nautilus_trader.adapters.binance.common.enums import BinanceAccountType

# Dry-run execution client
exec_config = BinanceExecClientConfig(
    api_key=os.environ["BINANCE_API_KEY"],
    api_secret=os.environ["BINANCE_API_SECRET"],
    account_type=BinanceAccountType.USDT_FUTURE,
    testnet=True,  # Use testnet endpoints

    # CRITICAL: Disable order submission
    submit_orders=False,
)
```

### Dry-Run Strategy Wrapper

```python
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.model.orders import Order

class DryRunStrategy(Strategy):
    """
    Wrapper that logs orders instead of submitting them.
    Tracks hypothetical P&L for validation.
    """

    def __init__(self, config, inner_strategy: Strategy):
        super().__init__(config)
        self.inner = inner_strategy
        self.hypothetical_orders: list[dict] = []
        self.hypothetical_pnl = 0.0

    def on_start(self):
        self.inner.on_start()

    def on_bar(self, bar):
        self.inner.on_bar(bar)

    def submit_order(self, order: Order) -> None:
        """Intercept and log order instead of submitting."""
        order_info = {
            "timestamp": self.clock.utc_now(),
            "instrument_id": str(order.instrument_id),
            "side": str(order.side),
            "quantity": str(order.quantity),
            "order_type": str(order.order_type),
            "price": str(order.price) if order.price else "MARKET",
        }
        self.hypothetical_orders.append(order_info)

        self._log.info(f"[DRY-RUN] Would submit: {order_info}")

        # Track hypothetical fill at current price
        if bar := self.cache.bar(order.instrument_id):
            fill_price = bar.close
            self._update_hypothetical_pnl(order, fill_price)

    def _update_hypothetical_pnl(self, order: Order, fill_price: float):
        """Track hypothetical P&L assuming immediate fill."""
        # Implementation depends on position tracking logic
        pass

    def on_stop(self):
        self._log.info(f"[DRY-RUN] Total hypothetical orders: {len(self.hypothetical_orders)}")
        self._log.info(f"[DRY-RUN] Hypothetical P&L: {self.hypothetical_pnl}")
        self.inner.on_stop()
```

### Running Dry-Run

```bash
# Using Makefile target
make dry-run STRATEGY=momentum VENUE=binance DURATION=72h

# Or directly
python scripts/run_dry_run.py \
    --strategy momentum \
    --venue binance \
    --duration 72h \
    --log-level DEBUG
```

### Dry-Run Validation Metrics

```python
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class DryRunMetrics:
    """Metrics to validate before progressing to shadow."""

    # Stability
    uptime_hours: float
    error_count: int
    restart_count: int

    # Performance
    avg_signal_latency_ms: float
    max_signal_latency_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float

    # Strategy
    signals_generated: int
    orders_would_submit: int

    def validate(self) -> tuple[bool, list[str]]:
        """Validate metrics against thresholds."""
        issues = []

        if self.uptime_hours < 72:
            issues.append(f"Insufficient uptime: {self.uptime_hours}h < 72h required")
        if self.error_count > 0:
            issues.append(f"Errors detected: {self.error_count}")
        if self.avg_signal_latency_ms > 100:
            issues.append(f"High avg latency: {self.avg_signal_latency_ms}ms > 100ms")
        if self.max_signal_latency_ms > 500:
            issues.append(f"Latency spike: {self.max_signal_latency_ms}ms > 500ms")
        if self.memory_usage_mb > 4096:
            issues.append(f"High memory: {self.memory_usage_mb}MB > 4GB")

        return len(issues) == 0, issues
```

---

## Stage 2: Shadow Trading

Shadow trading runs the strategy alongside production, tracking what orders *would* execute vs actual market outcomes.

### Shadow Configuration

```python
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode

class ShadowTradingNode:
    """
    Shadow node that tracks hypothetical executions against real market.
    Measures fill rate assumptions and slippage estimates.
    """

    def __init__(self, config: TradingNodeConfig, strategy):
        self.node = TradingNode(config=config)
        self.strategy = strategy

        # Shadow tracking
        self.hypothetical_orders: list = []
        self.hypothetical_fills: list = []
        self.tracking_errors: list = []

    def track_hypothetical_fill(self, order, market_data):
        """
        Simulate fill against actual market data.
        Track slippage from backtest assumptions.
        """
        # For market orders: use next trade price
        # For limit orders: check if price level was touched
        if order.order_type == "MARKET":
            fill_price = market_data.last_trade_price
            slippage_bps = abs(fill_price - order.expected_price) / order.expected_price * 10000
        else:
            # Limit order - check book depth
            fill_price, filled = self._simulate_limit_fill(order, market_data)
            slippage_bps = 0 if filled else None

        self.hypothetical_fills.append({
            "order_id": order.id,
            "expected_price": order.expected_price,
            "actual_price": fill_price,
            "slippage_bps": slippage_bps,
            "filled": filled if order.order_type == "LIMIT" else True,
        })

    def calculate_tracking_error(self) -> float:
        """
        Calculate tracking error between hypothetical and backtest P&L.
        Target: < 2% over 7 days.
        """
        hypothetical_returns = self._calculate_hypothetical_returns()
        backtest_returns = self._load_backtest_returns()

        tracking_error = np.std(hypothetical_returns - backtest_returns) * np.sqrt(252)
        return tracking_error
```

### Shadow Metrics

```python
@dataclass
class ShadowMetrics:
    """Metrics to validate before progressing to paper trading."""

    # Tracking
    tracking_error_percent: float  # Annualized tracking error vs backtest
    fill_rate_actual: float        # % of orders that would have filled
    fill_rate_assumed: float       # % assumed in backtest

    # Slippage
    avg_slippage_bps: float
    max_slippage_bps: float
    slippage_vs_assumed_bps: float  # Difference from backtest assumption

    # Market impact
    orders_that_moved_market: int
    estimated_market_impact_bps: float

    def validate(self) -> tuple[bool, list[str]]:
        issues = []

        if self.tracking_error_percent > 2.0:
            issues.append(f"High tracking error: {self.tracking_error_percent}% > 2%")
        if abs(self.fill_rate_actual - self.fill_rate_assumed) > 0.1:
            issues.append(f"Fill rate mismatch: {self.fill_rate_actual} vs {self.fill_rate_assumed}")
        if self.slippage_vs_assumed_bps > 5:
            issues.append(f"Slippage exceeds assumption by {self.slippage_vs_assumed_bps}bps")

        return len(issues) == 0, issues
```

### Running Shadow Mode

```bash
# Using Makefile target
make shadow-run STRATEGY=momentum VENUE=binance DURATION=7d

# Monitor shadow metrics
make shadow-metrics
```

---

## Stage 3: Paper Trading (Testnet)

Paper trading uses exchange testnet APIs to submit real orders with fake funds.

### Exchange Testnet Configuration

```python
# Binance Futures Testnet
binance_testnet_exec = BinanceExecClientConfig(
    api_key=os.environ["BINANCE_TESTNET_API_KEY"],
    api_secret=os.environ["BINANCE_TESTNET_API_SECRET"],
    account_type=BinanceAccountType.USDT_FUTURE,
    testnet=True,
    base_url_http="https://testnet.binancefuture.com",
    base_url_ws="wss://stream.binancefuture.com",
)

# Bybit Testnet
bybit_testnet_exec = BybitExecClientConfig(
    api_key=os.environ["BYBIT_TESTNET_API_KEY"],
    api_secret=os.environ["BYBIT_TESTNET_API_SECRET"],
    account_type=BybitAccountType.UNIFIED,
    testnet=True,
    base_url_http="https://api-testnet.bybit.com",
)

# OKX Demo Trading
okx_demo_exec = OKXExecClientConfig(
    api_key=os.environ["OKX_DEMO_API_KEY"],
    api_secret=os.environ["OKX_DEMO_API_SECRET"],
    passphrase=os.environ["OKX_DEMO_PASSPHRASE"],
    account_type=OKXAccountType.UNIFIED,
    is_demo=True,
)

# dYdX Testnet
dydx_testnet_exec = DYDXExecClientConfig(
    wallet_address=os.environ["DYDX_TESTNET_WALLET"],
    mnemonic=os.environ["DYDX_TESTNET_MNEMONIC"],  # OK for testnet
    is_testnet=True,
)
```

### Paper Trading Configuration

```python
paper_config = TradingNodeConfig(
    trader_id="PAPER-001",
    instance_id="PAPER-001",

    log_level="INFO",
    log_level_file="DEBUG",
    log_file_path="logs/paper/",

    # Enable cache for state persistence
    cache_database=CacheDatabaseConfig(
        type="redis",
        host="localhost",
        port=6379,
        db=1,  # Separate DB from production
    ),

    # Enable reconciliation
    exec_engine=LiveExecEngineConfig(
        reconciliation=True,
        reconciliation_lookback_mins=1440,
    ),
)
```

### Paper Trading Validation

```python
@dataclass
class PaperTradingMetrics:
    """Metrics to validate before production deployment."""

    # Performance
    total_pnl: float
    sharpe_ratio: float
    max_drawdown_percent: float
    win_rate: float

    # Execution
    total_trades: int
    avg_fill_time_ms: float
    rejected_orders: int

    # Risk
    max_position_size: float
    max_daily_loss: float
    margin_utilization_max: float

    # Operations
    uptime_percent: float
    reconnections: int

    def validate(self, limits: dict) -> tuple[bool, list[str]]:
        issues = []

        if self.total_pnl < 0:
            issues.append(f"Negative P&L: {self.total_pnl}")
        if self.max_drawdown_percent > limits.get("max_drawdown", 10):
            issues.append(f"Drawdown exceeded: {self.max_drawdown_percent}%")
        if self.rejected_orders > limits.get("max_rejected", 10):
            issues.append(f"Too many rejected orders: {self.rejected_orders}")
        if self.uptime_percent < 99.5:
            issues.append(f"Low uptime: {self.uptime_percent}%")

        return len(issues) == 0, issues
```

### Running Paper Trading

```bash
# Using Makefile target
make paper-trade STRATEGY=momentum VENUE=binance-testnet DURATION=14d

# Monitor paper trading
make paper-metrics
make paper-report
```

---

## Stage 4: Production Deployment

### Pre-Production Checklist

```markdown
## Production Deployment Checklist

### Security
- [ ] API keys rotated from testnet
- [ ] IP whitelisting configured
- [ ] Secrets in Vault/KMS (not .env)
- [ ] MFA enabled on exchange accounts
- [ ] Withdrawal addresses whitelisted

### Infrastructure
- [ ] Redis persistence configured (AOF)
- [ ] Log rotation configured
- [ ] Monitoring dashboards deployed
- [ ] Alerting rules configured
- [ ] Backup procedures tested

### Risk Controls
- [ ] Position limits configured
- [ ] Daily loss limits set
- [ ] Circuit breakers tested
- [ ] Kill switch accessible
- [ ] Emergency contacts documented

### Operations
- [ ] Runbook reviewed
- [ ] On-call rotation set
- [ ] Escalation procedures documented
- [ ] DR plan tested
- [ ] Rollback procedure documented

### Approvals
- [ ] Strategy performance reviewed
- [ ] Risk committee approval
- [ ] Compliance sign-off (if required)
```

### Production Configuration

⚠️ **CRITICAL**: Production must use Vault/KMS for secrets. See [SECURITY.md](SECURITY.md) for details.

```python
from nautilus_trader.config import TradingNodeConfig, CacheDatabaseConfig
import hvac  # HashiCorp Vault client

# =============================================================================
# PRODUCTION SECRETS RETRIEVAL - VAULT/KMS REQUIRED
# =============================================================================
def get_secrets_from_vault() -> dict:
    """
    Retrieve secrets from HashiCorp Vault.
    NEVER use environment variables for production secrets.
    """
    client = hvac.Client(
        url=os.environ["VAULT_ADDR"],
        token=os.environ["VAULT_TOKEN"],  # Or use AppRole/K8s auth
    )

    # Read secrets from Vault
    secret_response = client.secrets.kv.v2.read_secret_version(
        path="nautilus/production",
        mount_point="secret",
    )

    return secret_response["data"]["data"]


# Alternative: AWS KMS/Secrets Manager
def get_secrets_from_aws() -> dict:
    """Retrieve secrets from AWS Secrets Manager."""
    import boto3
    import json

    client = boto3.client("secretsmanager", region_name="us-east-1")
    response = client.get_secret_value(SecretId="nautilus/production")
    return json.loads(response["SecretString"])


# Get secrets at startup (not from env vars!)
secrets = get_secrets_from_vault()  # Or get_secrets_from_aws()

production_config = TradingNodeConfig(
    trader_id="PROD-001",
    instance_id=f"PROD-{os.environ['HOSTNAME']}",

    # Logging
    log_level="INFO",
    log_level_file="INFO",
    log_file_path="/var/log/nautilus/",
    log_component_levels={
        "ExecEngine": "DEBUG",  # Verbose execution logging
        "RiskEngine": "DEBUG",
    },

    # Redis with authentication from Vault
    cache_database=CacheDatabaseConfig(
        type="redis",
        host=secrets["redis_host"],
        port=6379,
        db=0,
        password=secrets["redis_password"],  # From Vault, NOT env var
        ssl=True,
    ),

    # Execution
    exec_engine=LiveExecEngineConfig(
        reconciliation=True,
        reconciliation_lookback_mins=1440,
        filter_unclaimed_external_orders=True,
    ),

    # Timeouts
    timeout_connection=30.0,
    timeout_reconciliation=60.0,
    timeout_portfolio=10.0,
    timeout_disconnection=10.0,
)
```

### Production Risk Controls

```python
from nautilus_trader.risk.engine import RiskEngine
from nautilus_trader.config import RiskEngineConfig

risk_config = RiskEngineConfig(
    # Position limits
    max_order_submit_rate="100/00:00:01",  # 100 orders/second
    max_order_modify_rate="100/00:00:01",
    max_notional_per_order={"USDT": 100_000},

    # Exposure limits
    max_position_size={"BTCUSDT-PERP.BINANCE": 10.0},
    max_cumulative_notional={"USDT": 1_000_000},
)

# Additional custom risk checks
class ProductionRiskManager:
    """Production risk controls beyond built-in limits."""

    def __init__(self, config: dict):
        self.max_daily_loss = config["max_daily_loss"]
        self.max_drawdown = config["max_drawdown"]
        self.circuit_breaker_threshold = config["circuit_breaker_threshold"]

        self.daily_pnl = 0.0
        self.peak_equity = 0.0
        self.current_equity = 0.0
        self.circuit_breaker_triggered = False

    def check_daily_loss(self, pnl_update: float) -> bool:
        """Check if daily loss limit breached."""
        self.daily_pnl += pnl_update
        if self.daily_pnl < -self.max_daily_loss:
            self._trigger_circuit_breaker("Daily loss limit breached")
            return False
        return True

    def check_drawdown(self, equity: float) -> bool:
        """Check if drawdown limit breached."""
        self.current_equity = equity
        self.peak_equity = max(self.peak_equity, equity)

        drawdown = (self.peak_equity - self.current_equity) / self.peak_equity
        if drawdown > self.max_drawdown:
            self._trigger_circuit_breaker("Drawdown limit breached")
            return False
        return True

    def _trigger_circuit_breaker(self, reason: str):
        """Trigger circuit breaker - flatten all positions."""
        self.circuit_breaker_triggered = True
        logger.critical(f"CIRCUIT BREAKER: {reason}")
        self._send_alert(reason)
        self._flatten_all_positions()

    def _send_alert(self, reason: str):
        """Send alert via configured channels."""
        import requests

        # PagerDuty alert
        if pagerduty_key := os.environ.get("PAGERDUTY_ROUTING_KEY"):
            requests.post(
                "https://events.pagerduty.com/v2/enqueue",
                json={
                    "routing_key": pagerduty_key,
                    "event_action": "trigger",
                    "payload": {
                        "summary": f"NautilusTrader Circuit Breaker: {reason}",
                        "severity": "critical",
                        "source": "nautilus-prod",
                    },
                },
                timeout=5,
            )

        # Slack webhook
        if slack_url := os.environ.get("SLACK_WEBHOOK_URL"):
            requests.post(
                slack_url,
                json={"text": f"🚨 CIRCUIT BREAKER TRIGGERED: {reason}"},
                timeout=5,
            )

    def _flatten_all_positions(self):
        """
        Close all open positions immediately.
        Uses market orders for fastest execution.
        """
        for position in self.strategy.cache.positions():
            if position.is_open:
                # Create closing order
                close_order = self.strategy.order_factory.market(
                    instrument_id=position.instrument_id,
                    order_side=OrderSide.SELL if position.side == PositionSide.LONG else OrderSide.BUY,
                    quantity=position.quantity,
                    reduce_only=True,
                )
                self.strategy.submit_order(close_order)
                logger.warning(f"Flattening position: {position.instrument_id}")

        # Cancel all open orders
        for order in self.strategy.cache.orders_open():
            self.strategy.cancel_order(order)
            logger.warning(f"Cancelling order: {order.client_order_id}")
```

### Production Monitoring

```python
from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Metrics
orders_submitted = Counter('nautilus_orders_submitted_total', 'Total orders submitted', ['venue', 'side'])
orders_filled = Counter('nautilus_orders_filled_total', 'Total orders filled', ['venue', 'side'])
order_latency = Histogram('nautilus_order_latency_seconds', 'Order submission to fill latency')
position_value = Gauge('nautilus_position_value', 'Current position value', ['instrument'])
daily_pnl = Gauge('nautilus_daily_pnl', 'Daily P&L')
drawdown = Gauge('nautilus_drawdown', 'Current drawdown from peak')

# Start metrics server
start_http_server(8000)

class MetricsPublisher:
    """Publish trading metrics to Prometheus."""

    def on_order_submitted(self, order):
        orders_submitted.labels(
            venue=str(order.instrument_id.venue),
            side=str(order.side),
        ).inc()

    def on_order_filled(self, order, fill_time_ns):
        orders_filled.labels(
            venue=str(order.instrument_id.venue),
            side=str(order.side),
        ).inc()
        order_latency.observe(fill_time_ns / 1e9)

    def update_position(self, instrument_id, value):
        position_value.labels(instrument=str(instrument_id)).set(value)

    def update_pnl(self, pnl, dd):
        daily_pnl.set(pnl)
        drawdown.set(dd)
```

### Alerting Configuration

```yaml
# alertmanager.yml
groups:
  - name: nautilus_alerts
    rules:
      - alert: HighLatency
        expr: histogram_quantile(0.99, nautilus_order_latency_seconds_bucket) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High order latency detected"

      - alert: CircuitBreakerTriggered
        expr: nautilus_circuit_breaker_triggered == 1
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker triggered - all trading halted"

      - alert: DrawdownExceeded
        expr: nautilus_drawdown > 0.1
        labels:
          severity: critical
        annotations:
          summary: "Drawdown exceeded 10%"

      - alert: ConnectionLost
        expr: nautilus_websocket_connected == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Exchange WebSocket disconnected"
```

---

## Deployment Scripts

### Deploy to Production

```bash
#!/bin/bash
# scripts/deploy_production.sh

set -e

STRATEGY=$1
VENUE=$2
VERSION=$(git describe --tags --always)

echo "=== Production Deployment ==="
echo "Strategy: $STRATEGY"
echo "Venue: $VENUE"
echo "Version: $VERSION"

# Pre-flight checks
echo "Running pre-flight checks..."
make pre-flight-check

# Confirm deployment
read -p "Proceed with production deployment? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled"
    exit 1
fi

# Deploy
echo "Deploying..."
docker-compose -f docker/production.yml up -d

# Verify
echo "Verifying deployment..."
sleep 10
make health-check

echo "=== Deployment Complete ==="
echo "Monitor: make live-monitor"
```

### Emergency Stop

⚠️ **CRITICAL**: Emergency stop API requires authentication. Store API key in Vault.

```bash
#!/bin/bash
# scripts/emergency_stop.sh

set -e

echo "!!! EMERGENCY STOP !!!"
echo "This will:"
echo "  1. Cancel all open orders"
echo "  2. Flatten all positions"
echo "  3. Stop all trading"

read -p "Type 'STOP' to confirm: " CONFIRM
if [ "$CONFIRM" != "STOP" ]; then
    echo "Aborted"
    exit 1
fi

# Get API key from Vault (never hardcode!)
API_KEY=$(vault kv get -field=emergency_api_key secret/nautilus/production)

# Trigger emergency stop via authenticated API with timeout
echo "Triggering emergency stop..."
HTTP_CODE=$(curl -s -o /tmp/emergency_response.txt -w "%{http_code}" \
    --connect-timeout 5 \
    --max-time 10 \
    -X POST \
    -H "Authorization: Bearer ${API_KEY}" \
    -H "Content-Type: application/json" \
    http://localhost:8080/api/emergency-stop)

if [ "$HTTP_CODE" != "200" ]; then
    echo "WARNING: API call failed with HTTP $HTTP_CODE"
    echo "Falling back to direct container stop..."
fi

# Always stop containers as fallback/confirmation
docker-compose -f docker/production.yml down

echo "Emergency stop complete"
echo "IMPORTANT: Verify positions manually on exchange!"
echo "Exchange dashboards:"
echo "  - Binance: https://www.binance.com/en/futures"
echo "  - Bybit: https://www.bybit.com/trade/usdt/BTCUSDT"
```

---

## Docker Deployment

### Production Docker Compose

```yaml
# docker/production.yml
# Note: Remove deprecated 'version' field for modern Docker Compose

services:
  nautilus:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    environment:
      - ENVIRONMENT=production
      - REDIS_HOST=redis
      - VAULT_ADDR=${VAULT_ADDR}  # Secrets from Vault, not env vars
    secrets:
      - vault_token  # Only Vault token passed, secrets fetched at runtime
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    # CRITICAL: Resource limits prevent runaway processes
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "10"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - internal
      - monitoring

  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD} --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
        reservations:
          memory: 1G
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "${REDIS_PASSWORD}", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    networks:
      - internal

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 2G
    networks:
      - monitoring

  grafana:
    image: grafana/grafana:latest
    secrets:
      - grafana_admin_password
    environment:
      - GF_SECURITY_ADMIN_PASSWORD__FILE=/run/secrets/grafana_admin_password
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards
    ports:
      - "127.0.0.1:3000:3000"  # Bind to localhost only
    restart: unless-stopped
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 1G
    networks:
      - monitoring

secrets:
  vault_token:
    external: true
  grafana_admin_password:
    external: true

volumes:
  redis_data:
  prometheus_data:
  grafana_data:

networks:
  internal:
    driver: bridge
    internal: true  # No external access
  monitoring:
    driver: bridge
```

### Dockerfile

```dockerfile
# docker/Dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (for nautilus compilation)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Health check endpoint
EXPOSE 8080

# Run
CMD ["python", "-m", "nautilus_trader.live", "--config", "/app/config/production.toml"]
```

---

## Disaster Recovery

### Backup Procedures

```bash
#!/bin/bash
# scripts/backup.sh

set -e

BACKUP_DIR="/backups/nautilus/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR/logs"

# Get Redis password from Vault (NEVER hardcode!)
REDIS_PASSWORD=$(vault kv get -field=redis_password secret/nautilus/production)
export REDISCLI_AUTH="$REDIS_PASSWORD"

# Backup Redis with authentication
echo "Backing up Redis..."
redis-cli --rdb "$BACKUP_DIR/redis.rdb"

# Verify Redis backup integrity
if [ ! -f "$BACKUP_DIR/redis.rdb" ] || [ ! -s "$BACKUP_DIR/redis.rdb" ]; then
    echo "ERROR: Redis backup failed or empty!"
    exit 1
fi

# Generate checksum for verification
sha256sum "$BACKUP_DIR/redis.rdb" > "$BACKUP_DIR/redis.rdb.sha256"

# Backup configuration (exclude secrets!)
echo "Backing up configuration..."
cp -r config/ "$BACKUP_DIR/config/"
# Remove any accidentally included secrets
find "$BACKUP_DIR/config/" -name "*.env" -delete
find "$BACKUP_DIR/config/" -name "*secret*" -delete

# Backup logs (last 7 days)
echo "Backing up logs..."
find logs/ -mtime -7 -name "*.log" -exec cp {} "$BACKUP_DIR/logs/" \;

# Create manifest with checksums
echo "Creating backup manifest..."
find "$BACKUP_DIR" -type f -exec sha256sum {} \; > "$BACKUP_DIR/MANIFEST.sha256"

# Upload to S3 with server-side encryption
echo "Uploading to S3..."
aws s3 sync "$BACKUP_DIR" "s3://nautilus-backups/$(date +%Y%m%d)/" \
    --sse AES256 \
    --storage-class STANDARD_IA

echo "Backup complete: $BACKUP_DIR"
echo "Verify with: aws s3 ls s3://nautilus-backups/$(date +%Y%m%d)/"
```

### Recovery Procedure

```markdown
## Recovery Runbook

### Scenario: Node Failure

1. **Assess**
   - Check monitoring for failure cause
   - Verify no open positions/orders on exchange

2. **Recover**
   ```bash
   # Start new instance
   docker-compose -f docker/production.yml up -d

   # Wait for startup
   sleep 30

   # Verify health
   make health-check

   # Reconcile positions
   make reconcile-positions
   ```

3. **Verify**
   - Check positions match exchange
   - Verify order state
   - Check P&L tracking

### Scenario: Exchange Disconnection

1. **Automatic**: Node will attempt reconnection
2. **Manual** (if > 5 min):
   ```bash
   # Check exchange status
   make exchange-status

   # Force reconnect
   make reconnect VENUE=binance

   # If still failing, stop and flatten
   make emergency-stop
   ```

### Scenario: Data Corruption

1. **Stop trading**
   ```bash
   make trading-pause
   ```

2. **Restore from backup**
   ```bash
   # Find latest clean backup
   aws s3 ls s3://nautilus-backups/ --recursive | tail -10

   # Restore Redis
   redis-cli shutdown
   cp /backups/redis.rdb /var/lib/redis/dump.rdb
   systemctl start redis
   ```

3. **Reconcile with exchange**
   ```bash
   make reconcile-positions
   make reconcile-orders
   ```

4. **Resume trading**
   ```bash
   make trading-resume
   ```
```

---

## Rollback Procedure

```bash
#!/bin/bash
# scripts/rollback.sh

PREVIOUS_VERSION=$1

if [ -z "$PREVIOUS_VERSION" ]; then
    echo "Usage: rollback.sh <version>"
    echo "Available versions:"
    docker images nautilus --format "{{.Tag}}"
    exit 1
fi

echo "Rolling back to $PREVIOUS_VERSION"

# Stop current
docker-compose -f docker/production.yml down

# Update image tag
export NAUTILUS_VERSION=$PREVIOUS_VERSION

# Start previous version
docker-compose -f docker/production.yml up -d

# Verify
sleep 30
make health-check

echo "Rollback complete"
```

---

## Operational Procedures

### Daily Operations

```markdown
## Daily Checklist

### Morning (Pre-Market)
- [ ] Check overnight P&L and positions
- [ ] Review error logs for anomalies
- [ ] Verify exchange connectivity
- [ ] Check funding rates (if holding perpetuals)
- [ ] Review market conditions

### During Trading
- [ ] Monitor latency metrics (< 100ms avg)
- [ ] Check position limits utilization
- [ ] Review fill quality vs expected
- [ ] Watch for unusual market conditions

### Evening (Post-Market)
- [ ] Generate daily report
- [ ] Review all trades
- [ ] Check P&L reconciliation
- [ ] Backup state
- [ ] Review alerts
```

### Weekly Operations

```markdown
## Weekly Checklist

- [ ] Review weekly performance vs benchmark
- [ ] Analyze strategy metrics
- [ ] Check for software updates
- [ ] Review and rotate logs
- [ ] Test backup restoration
- [ ] Update documentation if needed
```

---

## Next Steps

1. **Configure exchanges**: [CONFIGURATION.md](CONFIGURATION.md)
2. **Set up data feeds**: [DATA_INGESTION.md](DATA_INGESTION.md)
3. **Build strategies**: [STRATEGY_DEVELOPMENT.md](STRATEGY_DEVELOPMENT.md)
4. **Run backtests**: [BACKTESTING.md](BACKTESTING.md)
5. **Validate statistically**: [QUANTITATIVE_VALIDATION.md](QUANTITATIVE_VALIDATION.md)
6. **Security hardening**: [SECURITY.md](SECURITY.md)
