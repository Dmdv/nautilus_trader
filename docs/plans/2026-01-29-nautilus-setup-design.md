# NautilusTrader Setup & Development Design

**Date:** 2026-01-29
**Status:** REVISED (v2) - Addressing validation feedback
**Author:** Claude Code + User Collaboration
**Revision:** v2.0 - Security hardening, quant rigor, operational completeness

## Overview

This design document outlines the complete setup for NautilusTrader development and production deployment focused on crypto trading across Binance, Bybit, OKX, and dYdX exchanges.

## Requirements Summary

| Aspect | Specification |
|--------|---------------|
| **Goal** | Learn + Develop Custom Strategies + Production Deploy |
| **Markets** | Crypto only |
| **Experience Level** | Advanced (quant + dev + trading frameworks) |
| **Exchanges** | Binance (Spot+Futures), Bybit (Derivatives), OKX (Spot+Futures), dYdX |
| **Data Pipeline** | Local Parquet catalog + Tardis streaming + existing data import |
| **Strategy Types** | Trend-following, Market Making, Statistical Arbitrage |
| **Python Version** | 3.13 |
| **Rust Version** | Latest stable |

---

## Deliverables

### Documentation Structure

```
docs/
├── README.md                    # Navigation hub linking all guides
├── plans/
│   └── 2026-01-29-nautilus-setup-design.md  # This document
├── SETUP.md                     # Local build & installation
├── CONFIGURATION.md             # Exchange credentials, logging, tuning
├── SECURITY.md                  # Secrets management, IP whitelisting (NEW)
├── DATA_INGESTION.md            # Tardis, Parquet catalog, imports
├── STRATEGY_DEVELOPMENT.md      # Patterns for trend/MM/arb strategies
├── BACKTESTING.md               # BacktestEngine vs BacktestNode, walk-forward
├── QUANTITATIVE_VALIDATION.md   # Monte Carlo, regime detection, stat tests (NEW)
└── DEPLOYMENT.md                # Dry-run, shadow, paper, testnet, mainnet progression
```

### Makefile Targets (42 total - expanded from 28)

#### Setup (6 targets)
| Target | Description |
|--------|-------------|
| `install` | Install release build (optimized) |
| `install-debug` | Install debug build (with symbols) |
| `install-dev` | Install with dev dependencies |
| `install-highprec` | Install with 128-bit decimal precision |
| `clean` | Remove build artifacts and caches |
| `env-check` | Verify Python, Rust, and dependencies |

#### Testing (5 targets - NEW)
| Target | Description |
|--------|-------------|
| `test` | Run all tests |
| `test-unit` | Run unit tests only |
| `test-integration` | Run integration tests |
| `lint` | Run linters (ruff, mypy) |
| `typecheck` | Run type checking (mypy strict) |

#### Configuration (3 targets)
| Target | Description |
|--------|-------------|
| `config-check` | Validate .env and API connectivity |
| `config-template` | Generate .env.template with all variables |
| `credentials-test` | Test exchange API credentials (read-only) |

#### Security (4 targets - NEW)
| Target | Description |
|--------|-------------|
| `secrets-check` | Audit secrets for plaintext exposure |
| `secrets-rotate` | Guide for rotating API keys |
| `ip-whitelist-verify` | Verify IP whitelisting on exchanges |
| `security-audit` | Full security posture check |

#### Data (6 targets - expanded)
| Target | Description |
|--------|-------------|
| `tardis-download` | Download historical data from Tardis |
| `tardis-sync` | Sync latest data to catalog |
| `data-import` | Import CSV/existing files to catalog |
| `data-catalog-info` | Show catalog statistics |
| `data-validate` | Check data integrity and gaps |
| `data-download-range` | Download data for specific date range |

#### Strategy (4 targets - expanded)
| Target | Description |
|--------|-------------|
| `strategy-new` | Scaffold new strategy from template |
| `strategy-lint` | Lint strategy code |
| `strategy-test` | Run strategy unit tests |
| `strategy-validate` | Validate strategy config before execution |

#### Backtesting (6 targets - expanded)
| Target | Description |
|--------|-------------|
| `backtest-run` | Run backtest from config file |
| `backtest-sweep` | Parameter optimization sweep |
| `backtest-walkforward` | Run walk-forward analysis |
| `backtest-montecarlo` | Run Monte Carlo validation |
| `backtest-report` | Generate performance report |
| `backtest-compare` | Compare multiple backtest runs |

#### Live Trading (8 targets - expanded)
| Target | Description |
|--------|-------------|
| `dry-run` | Live data, simulated execution |
| `dry-run-status` | Check dry-run node status |
| `shadow-run` | Orders logged but not submitted (NEW) |
| `live-paper` | Run paper trading (testnet) |
| `live-prod` | Run production (mainnet) - requires preflight |
| `live-status` | Check running node status |
| `live-stop` | Graceful shutdown |
| `exchange-status` | Check connectivity to all exchanges |

#### Operations (6 targets - NEW)
| Target | Description |
|--------|-------------|
| `health-check` | System health verification |
| `backup-state` | Backup Redis state and configs |
| `restore-state` | Restore from backup |
| `logs-tail` | Tail live trading logs |
| `metrics-export` | Export Prometheus metrics |
| `circuit-breaker-status` | Check circuit breaker state |

#### Docker (2 targets)
| Target | Description |
|--------|-------------|
| `docker-build` | Build production Docker image (multi-arch) |
| `docker-run` | Run in container with resource limits |

---

## Detailed Specifications

### 1. SETUP.md - Local Build & Installation

#### Prerequisites
- Python 3.13
- Rust (latest stable via rustup)
- Build tools: clang, cmake, pkg-config
- Package manager: `uv` (recommended) or Poetry
- Redis 7.0+ (for production state management)

#### Installation Approaches

| Approach | Use Case | Command |
|----------|----------|---------|
| Binary wheel | Quick start, no modifications | `uv pip install nautilus_trader` |
| Source debug | Development, debugging | `make install-debug` |
| Source release | Production, performance testing | `make install` |
| High-precision | 128-bit decimal for DeFi/perpetuals | `make install-highprec` |

#### Resource Requirements

| Mode | CPU | RAM | Disk | Network |
|------|-----|-----|------|---------|
| Backtest (small) | 2 cores | 4GB | 10GB | None |
| Backtest (large) | 8+ cores | 32GB | 500GB+ | None |
| Dry-run | 2 cores | 4GB | 10GB | 100Mbps |
| Paper trading | 4 cores | 8GB | 50GB | 100Mbps |
| Production | 8+ cores | 16GB+ | 100GB+ | 1Gbps, low latency |

#### Verification
```python
import nautilus_trader
print(nautilus_trader.__version__)
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.live.node import TradingNode
```

---

### 2. SECURITY.md - Secrets Management & Security (NEW)

#### ⚠️ CRITICAL: Credential Security

**NEVER store mnemonics or private keys in plaintext `.env` files for production.**

#### Secrets Management Tiers

| Tier | Use Case | Solution |
|------|----------|----------|
| Development | Local testing | `.env` file (gitignored) |
| Staging | Pre-production | sops-encrypted files |
| Production | Live trading | HashiCorp Vault or AWS Secrets Manager |

#### dYdX Key Security (CRITICAL)

dYdX uses a mnemonic that provides **full wallet control**. This requires special handling:

```python
# ❌ NEVER DO THIS IN PRODUCTION
DYDX_MNEMONIC=word1 word2 word3 ... word24

# ✅ OPTION 1: Hardware wallet (Ledger) - RECOMMENDED
# Connect via dYdX frontend, sign transactions via hardware

# ✅ OPTION 2: AWS KMS
# Store mnemonic in KMS, decrypt at runtime only
import boto3
kms = boto3.client('kms')
mnemonic = kms.decrypt(CiphertextBlob=encrypted_mnemonic)['Plaintext']

# ✅ OPTION 3: HashiCorp Vault
# Store in Vault, fetch at runtime with short TTL
import hvac
client = hvac.Client(url='https://vault.example.com')
mnemonic = client.secrets.kv.v2.read_secret_version(path='dydx')['data']['data']['mnemonic']

# ✅ OPTION 4: sops (minimum for staging)
# sops -d secrets.enc.yaml | yq '.dydx.mnemonic'
```

#### API Key Security by Exchange

| Exchange | Security Measures | Implementation |
|----------|-------------------|----------------|
| **Binance** | IP whitelist + separate read-only keys | Data client: read-only key; Exec client: trade key with IP lock |
| **Bybit** | IP whitelist + minimal permissions | Request only: Trade, Read permissions. Never: Withdraw |
| **OKX** | IP whitelist + passphrase + trade-only | IP lock mandatory; passphrase in secrets manager |
| **dYdX** | Hardware wallet or KMS | See above - mnemonic = full control |

#### IP Whitelisting (MANDATORY for Production)

**Binance:**
1. API Management → Edit restrictions → Restrict to trusted IPs
2. Add your server's static IP(s)
3. Verify: `make ip-whitelist-verify`

**Bybit:**
1. API → API Management → Edit → IP Restrictions
2. Enable "Restrict access to trusted IPs only"
3. Add server IPs

**OKX:**
1. API → Create API → IP Whitelist
2. Enter comma-separated IPs during creation
3. Cannot be modified after creation (must recreate)

**dYdX:**
- No IP whitelisting (wallet-based auth)
- Use hardware wallet or strict KMS policies

#### Environment Variables (Development Only)

```bash
# .env.template - Copy to .env, NEVER commit .env

# Binance (get from binance.com/en/my/settings/api-management)
BINANCE_API_KEY=
BINANCE_API_SECRET=
BINANCE_TESTNET=true  # Always start with testnet

# Bybit (get from bybit.com/app/user/api-management)
BYBIT_API_KEY=
BYBIT_API_SECRET=
BYBIT_TESTNET=true

# OKX (get from okx.com/account/my-api)
OKX_API_KEY=
OKX_API_SECRET=
OKX_PASSPHRASE=
OKX_TESTNET=true

# dYdX - FOR DEVELOPMENT/TESTNET ONLY
# Production: Use hardware wallet or KMS
DYDX_MNEMONIC=        # ONLY for testnet
DYDX_NETWORK=testnet  # testnet or mainnet

# Tardis (get from tardis.dev)
TARDIS_API_KEY=
```

---

### 3. CONFIGURATION.md - Exchange Configuration & System Tuning

#### Node Configuration Pattern

```python
from nautilus_trader.config import TradingNodeConfig, CacheDatabaseConfig

config = TradingNodeConfig(
    trader_id="TRADER-001",
    instance_id="INSTANCE-001",

    # Logging
    log_level="INFO",  # DEBUG for development
    log_level_file="DEBUG",
    log_file_path="logs/",

    # Cache (Redis for production)
    cache_database=CacheDatabaseConfig(
        type="redis",
        host="localhost",
        port=6379,
        db=0,
    ),

    # Timeouts
    timeout_connection=30.0,  # 30s for dYdX, 10s for CEX
    timeout_reconciliation=60.0,
    timeout_portfolio=10.0,

    # Data engine
    data_engine=LiveDataEngineConfig(
        time_bars_build_with_no_updates=True,
        time_bars_timestamp_on_close=True,
    ),

    # Execution engine
    exec_engine=LiveExecEngineConfig(
        reconciliation=True,  # ALWAYS True for production
        reconciliation_lookback_mins=1440,  # 24 hours
    ),
)
```

#### Exchange-Specific Configuration

| Parameter | Binance | Bybit | OKX | dYdX |
|-----------|---------|-------|-----|------|
| `timeout_connection` | 10s | 10s | 10s | 30s |
| `timeout_reconciliation` | 30s | 30s | 30s | 60s |
| `position_mode` | one-way/hedge | one-way | net/long-short | cross |
| `account_type` | SPOT, MARGIN, FUTURES | UNIFIED, CONTRACT | SPOT, MARGIN, SWAP | CROSS |

#### Rate Limiting Configuration

| Exchange | Orders/sec | Requests/min | Weight Limit | Handling |
|----------|------------|--------------|--------------|----------|
| Binance | 10 | 1200 | 1200/min | Built-in backoff |
| Bybit | 50 | 120 | 120/5sec | Built-in backoff |
| OKX | 60 | 300 | 300/2sec | Built-in backoff |
| dYdX | 5 | 100 | N/A (L2 gas) | Gas estimation |

#### Redis Configuration (Production)

```yaml
# redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

---

### 4. DATA_INGESTION.md - Tardis, Parquet Catalog & Imports

#### Data Architecture
```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Tardis    │────▶│   Wrangler   │────▶│  Parquet Catalog │
│  (Stream)   │     │  (Transform) │     │   (Storage)      │
└─────────────┘     └──────────────┘     └─────────────────┘
       ▲                   ▲                      │
┌─────────────┐     ┌──────────────┐              ▼
│ Your CSVs   │────▶│  Converters  │     ┌─────────────────┐
│ (Existing)  │     │              │     │  BacktestEngine │
└─────────────┘     └──────────────┘     └─────────────────┘
```

#### Tardis Integration Specifics

**Tardis Machine API** is used (not raw WebSocket replay):

```python
# tardis-download implementation
from tardis_dev import datasets

datasets.download(
    exchange="binance-futures",
    data_types=["trades", "book_snapshot_5_100ms"],
    from_date="2024-01-01",
    to_date="2024-12-31",
    symbols=["BTCUSDT"],
    api_key=os.environ["TARDIS_API_KEY"],
    download_dir="data/raw/tardis",
)
```

**Transformation Pipeline:**
1. Tardis CSV → `TradeTickDataWrangler` or `OrderBookDeltaDataWrangler`
2. Wrangler output → NautilusTrader objects
3. Objects → `ParquetDataCatalog.write_data()`

#### Parquet Catalog Structure
```
data/catalog/
├── trade_tick/
│   └── BTCUSDT.BINANCE/2024/01/data.parquet
├── quote_tick/
│   └── ETHUSDT.BINANCE/2024/01/data.parquet
├── bar_1m/
│   └── BTCUSDT-PERP.BYBIT/2024/01/data.parquet
└── order_book_delta/
    └── BTC-USD.DYDX/2024/01/data.parquet
```

#### Data Types by Strategy (Enhanced)

| Strategy Type | Primary Data | Secondary Data | Auxiliary Data |
|---------------|--------------|----------------|----------------|
| **Trend-following** | OHLCV bars (1m-1h) | Volume profile | Funding rates, OI |
| **Market making** | L2 order book deltas | Trade ticks (flow toxicity) | Volatility regime |
| **Stat arb** | Quote ticks (multi-exchange) | Trade ticks, L2 books | Funding rates, transfer times |
| **Cross-exchange arb** | L2 books (both venues) | Network latency samples | Deposit/withdrawal status |

#### Storage Estimates

| Data Type | Size per Instrument per Day | 1 Year Storage |
|-----------|----------------------------|----------------|
| 1m bars | ~100KB | ~36MB |
| Trade ticks | ~50MB | ~18GB |
| Quote ticks | ~100MB | ~36GB |
| L2 order book (100ms) | ~500MB | ~180GB |

---

### 5. STRATEGY_DEVELOPMENT.md - Custom Strategy Patterns

#### Strategy Anatomy
```python
from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig

class MyStrategyConfig(StrategyConfig, frozen=True):
    instrument_id: str
    bar_type: str
    fast_ema_period: int = 10
    slow_ema_period: int = 20

class MyStrategy(Strategy):
    def __init__(self, config: MyStrategyConfig):
        super().__init__(config)
        self.instrument_id = InstrumentId.from_str(config.instrument_id)
        self.fast_ema = ExponentialMovingAverage(config.fast_ema_period)
        self.slow_ema = ExponentialMovingAverage(config.slow_ema_period)

    def on_start(self):
        self.subscribe_bars(BarType.from_str(self.config.bar_type))

    def on_bar(self, bar: Bar):
        self.fast_ema.update_raw(bar.close.as_double())
        self.slow_ema.update_raw(bar.close.as_double())

        if not self.slow_ema.initialized:
            return

        # Signal logic
        if self.fast_ema.value > self.slow_ema.value:
            if not self.portfolio.is_net_long(self.instrument_id):
                self.buy()
        elif self.fast_ema.value < self.slow_ema.value:
            if not self.portfolio.is_net_short(self.instrument_id):
                self.sell()

    def on_stop(self):
        self.cancel_all_orders(self.instrument_id)
        self.close_all_positions(self.instrument_id)
```

#### Market Making Strategy (Complete Specification)

```python
class MarketMakingConfig(StrategyConfig, frozen=True):
    instrument_id: str

    # Inventory management
    max_inventory_units: float = 10.0       # Hard position limit
    inventory_target: float = 0.0           # Neutral inventory target
    inventory_skew_factor: float = 0.001    # Quote adjustment per unit inventory

    # Adverse selection protection
    toxic_flow_detector: str = "vpin"       # VPIN or order_flow_imbalance
    toxic_flow_threshold: float = 0.7       # Pull quotes above this

    # Quote parameters
    base_spread_bps: float = 5.0            # Base spread in basis points
    spread_volatility_scalar: float = 2.0   # Multiply spread by vol regime
    min_spread_bps: float = 2.0             # Floor
    max_spread_bps: float = 50.0            # Ceiling

    # Risk limits
    max_daily_loss_pct: float = 1.0         # Daily loss limit
    max_position_holding_time: str = "1h"   # Force flatten if exceeded

    # Execution
    order_refresh_interval_ms: int = 100
    cancel_on_fill: bool = True             # Cancel opposite side on fill
    quote_levels: int = 3                   # Multi-level quoting

class MarketMakingStrategy(Strategy):
    """
    Implements Avellaneda-Stoikov market making with:
    - Inventory-based quote skewing
    - Adverse selection detection (VPIN)
    - Volatility-adaptive spreads
    - Multi-level quoting
    """

    def on_order_book_deltas(self, deltas: OrderBookDeltas):
        # Update order book state
        # Calculate mid-price, spread, depth
        # Detect adverse selection via VPIN
        # Update quotes with inventory skew
        pass

    def calculate_quote_skew(self) -> tuple[float, float]:
        """Avellaneda-Stoikov reservation price adjustment"""
        inventory = self.portfolio.net_position(self.instrument_id)
        gamma = self.config.inventory_skew_factor
        sigma = self.current_volatility
        T = self.time_to_end_of_session

        # Reservation price adjustment
        skew = -gamma * inventory * sigma**2 * T

        # Bid/ask adjustment
        bid_skew = skew - self.current_spread / 2
        ask_skew = skew + self.current_spread / 2

        return bid_skew, ask_skew
```

#### Statistical Arbitrage Strategy (Complete Specification)

```python
class StatArbConfig(StrategyConfig, frozen=True):
    leg1_instrument: str
    leg2_instrument: str

    # Cointegration testing
    cointegration_test: str = "johansen"    # or "engle_granger"
    min_cointegration_pvalue: float = 0.05
    lookback_for_cointegration: int = 252   # days
    retest_frequency: str = "weekly"        # Re-validate relationship

    # Spread analysis
    spread_zscore_entry: float = 2.0        # Enter when z-score exceeds
    spread_zscore_exit: float = 0.5         # Exit when z-score reverts
    spread_zscore_stop: float = 4.0         # Stop-loss on relationship breakdown
    half_life_max_days: int = 30            # Reject if mean-reversion too slow
    half_life_estimation: str = "ornstein_uhlenbeck"

    # Hedge ratio
    hedge_ratio_method: str = "kalman"      # Dynamic hedge ratio
    hedge_ratio_lookback: int = 60          # days

    # Stationarity monitoring
    hurst_exponent_max: float = 0.45        # Require mean-reverting (H < 0.5)
    adf_test_frequency: str = "daily"

    # Execution
    max_leg_slippage_bps: float = 5.0
    leg_execution_timeout_ms: int = 500
    rebalance_threshold_pct: float = 5.0    # Rebalance when hedge ratio drifts

class StatArbStrategy(Strategy):
    """
    Pairs trading with:
    - Johansen cointegration testing
    - Kalman filter for dynamic hedge ratio
    - Ornstein-Uhlenbeck half-life estimation
    - Rolling stationarity monitoring
    """

    def test_cointegration(self) -> bool:
        """Run Johansen cointegration test"""
        from statsmodels.tsa.vector_ar.vecm import coint_johansen

        result = coint_johansen(
            self.price_matrix,
            det_order=0,
            k_ar_diff=1
        )

        # Check trace statistic > critical value at 95%
        return result.trace_stat[0] > result.trace_stat_crit_vals[0, 1]

    def estimate_half_life(self) -> float:
        """Ornstein-Uhlenbeck half-life estimation"""
        spread = self.calculate_spread()
        spread_lag = spread.shift(1).dropna()
        spread_diff = spread.diff().dropna()

        # Regress spread_diff on spread_lag
        model = OLS(spread_diff, spread_lag)
        result = model.fit()

        theta = -result.params[0]  # Mean reversion speed
        half_life = np.log(2) / theta

        return half_life
```

#### Project Structure
```
strategies/
├── __init__.py
├── base/
│   ├── risk_manager.py          # Position sizing, stop-loss
│   └── circuit_breaker.py       # Emergency shutdown logic
├── trend/
│   ├── ema_cross.py
│   ├── breakout.py
│   └── configs/
│       └── ema_cross.yaml
├── market_making/
│   ├── basic_mm.py
│   ├── inventory_skew.py
│   ├── vpin_detector.py         # Adverse selection
│   └── configs/
│       └── mm_binance.yaml
├── arb/
│   ├── cross_exchange.py
│   ├── funding_arb.py
│   ├── cointegration.py         # Stat testing
│   └── configs/
│       └── btc_eth_pair.yaml
└── utils/
    ├── indicators.py
    └── signals.py
```

---

### 6. BACKTESTING.md - Engine Workflows & Validation

#### Two API Levels

| API | Use Case | Data Source | Best For |
|-----|----------|-------------|----------|
| `BacktestEngine` | Interactive, small data | In-memory | Research, prototyping, Jupyter |
| `BacktestNode` | Production, large data | Parquet streaming | Parameter sweeps, validation |

#### BacktestEngine Pattern
```python
engine = BacktestEngine(config=BacktestEngineConfig(
    trader_id="BACKTESTER-001",
    log_level="INFO",
))

# Venue configuration with realistic simulation
venue = Venue("BINANCE")
engine.add_venue(
    venue=venue,
    oms_type=OmsType.NETTING,
    account_type=AccountType.MARGIN,
    base_currency=USD,
    starting_balances=[Money(100_000, USDT)],

    # Realistic simulation settings
    fill_model=FillModel(
        prob_fill_on_limit=0.8,
        prob_fill_on_stop=0.9,
        prob_slippage=0.5,
        random_seed=42,
    ),
    latency_model=LatencyModel(
        base_latency_nanos=80_000_000,  # 80ms base
        insert_latency_nanos=10_000_000,
        update_latency_nanos=10_000_000,
        cancel_latency_nanos=10_000_000,
    ),
)

engine.add_instrument(instrument)
engine.add_data(bars)
engine.add_strategy(MyStrategy(config))
engine.run()
```

#### Exchange-Specific Simulation Parameters

```python
SIMULATION_CONFIGS = {
    "binance_spot": {
        "latency_base_ms": 80,
        "latency_std_ms": 30,
        "fill_prob_limit": 0.8,
        "fill_prob_stop": 0.9,
        "slippage_prob": 0.5,
        "slippage_bps": 2.0,
        "maker_prob": 0.7,
    },
    "binance_futures": {
        "latency_base_ms": 50,
        "latency_std_ms": 20,
        "fill_prob_limit": 0.85,
        "fill_prob_stop": 0.95,
        "slippage_prob": 0.4,
        "slippage_bps": 1.5,
        "maker_prob": 0.75,
    },
    "bybit_perp": {
        "latency_base_ms": 60,
        "latency_std_ms": 25,
        "fill_prob_limit": 0.8,
        "fill_prob_stop": 0.9,
        "slippage_prob": 0.5,
        "slippage_bps": 2.0,
        "maker_prob": 0.7,
    },
    "dydx_perp": {
        "latency_base_ms": 200,  # L2 settlement
        "latency_std_ms": 100,
        "fill_prob_limit": 0.7,
        "fill_prob_stop": 0.8,
        "slippage_prob": 0.6,
        "slippage_bps": 3.0,
        "maker_prob": 0.6,
        "gas_cost_per_trade_usd": 0.5,
    },
}
```

#### Walk-Forward Analysis (Complete Specification)

```python
class WalkForwardConfig:
    # Time windows
    train_period: str = "90d"           # In-sample training window
    test_period: str = "30d"            # Out-of-sample test window
    step_size: str = "30d"              # Roll forward increment
    anchored: bool = False              # False=rolling, True=expanding
    purge_gap: str = "1d"               # Gap between train/test (prevent lookahead)

    # Statistical requirements
    min_trades_per_window: int = 30     # Minimum for statistical significance
    min_windows: int = 12               # Minimum walk-forward windows

    # Optimization
    objective_function: str = "sharpe"  # sharpe, sortino, calmar, custom
    selection_method: str = "percentile_75"  # best, avg_top_n, percentile

    # Robustness checks
    parameter_stability_threshold: float = 0.3  # Max param variation across windows
    wfe_target: float = 0.5             # Walk-forward efficiency: OOS/IS performance

    # Constraints
    max_drawdown_pct: float = 20.0      # Reject params with DD > this
    min_profit_factor: float = 1.2      # Reject params with PF < this
```

Walk-forward validates strategy robustness by training on rolling windows:

```
|----Train----|--Purge--|--Test--|
      |----Train----|--Purge--|--Test--|
            |----Train----|--Purge--|--Test--|
```

**Walk-Forward Efficiency (WFE):**
```
WFE = Average OOS Sharpe / Average IS Sharpe

WFE > 0.5  = Good (strategy generalizes)
WFE < 0.3  = Poor (likely overfit)
```

---

### 7. QUANTITATIVE_VALIDATION.md - Statistical Rigor (NEW)

#### Monte Carlo Validation

```python
class MonteCarloConfig:
    n_permutations: int = 1000
    null_hypothesis: str = "random_entry_timing"  # or "random_returns"
    significance_level: float = 0.05
    random_seed: int = 42

def monte_carlo_validation(strategy_results, config: MonteCarloConfig) -> dict:
    """
    Test if strategy alpha is statistically significant vs random.

    Returns:
        - p_value: Probability of achieving results by chance
        - is_significant: True if p_value < significance_level
        - percentile: Where actual performance ranks vs permutations
    """
    actual_sharpe = strategy_results.sharpe_ratio

    permutation_sharpes = []
    for i in range(config.n_permutations):
        # Permute entry signals randomly
        permuted_results = run_with_permuted_signals(strategy_results)
        permutation_sharpes.append(permuted_results.sharpe_ratio)

    p_value = np.mean(np.array(permutation_sharpes) >= actual_sharpe)
    percentile = stats.percentileofscore(permutation_sharpes, actual_sharpe)

    return {
        "p_value": p_value,
        "is_significant": p_value < config.significance_level,
        "percentile": percentile,
        "actual_sharpe": actual_sharpe,
        "permutation_mean": np.mean(permutation_sharpes),
        "permutation_std": np.std(permutation_sharpes),
    }
```

#### Regime Detection

```python
class RegimeDetectionConfig:
    method: str = "hidden_markov"       # or "threshold", "change_point"
    n_states: int = 3                   # bull, bear, sideways
    features: list = ["returns_vol", "volume_regime", "trend_strength"]
    lookback_days: int = 252
    refit_frequency: str = "monthly"

def detect_market_regime(prices: pd.Series, config: RegimeDetectionConfig) -> pd.Series:
    """
    Identify market regimes using Hidden Markov Model.

    Returns:
        Series of regime labels (0=bear, 1=sideways, 2=bull)
    """
    from hmmlearn import hmm

    # Calculate features
    returns = prices.pct_change()
    volatility = returns.rolling(20).std()
    trend = prices.rolling(50).mean() / prices.rolling(200).mean()

    features = np.column_stack([returns, volatility, trend])

    model = hmm.GaussianHMM(n_components=config.n_states, covariance_type="full")
    model.fit(features)

    regimes = model.predict(features)
    return pd.Series(regimes, index=prices.index)
```

#### Bootstrap Confidence Intervals

```python
class BootstrapConfig:
    n_samples: int = 10000
    block_size: str = "auto"            # Stationary bootstrap for time series
    confidence_level: float = 0.95
    metrics: list = ["sharpe", "max_drawdown", "calmar", "win_rate"]

def bootstrap_confidence_intervals(returns: pd.Series, config: BootstrapConfig) -> dict:
    """
    Calculate confidence intervals for performance metrics using stationary bootstrap.

    Returns:
        Dict with CI bounds for each metric
    """
    from arch.bootstrap import StationaryBootstrap

    # Determine optimal block size
    if config.block_size == "auto":
        block_size = optimal_block_length(returns)
    else:
        block_size = int(config.block_size)

    bs = StationaryBootstrap(block_size, returns)

    results = {}
    for metric in config.metrics:
        metric_func = get_metric_function(metric)
        ci = bs.conf_int(metric_func, reps=config.n_samples, method="percentile")
        results[metric] = {
            "estimate": metric_func(returns),
            "ci_lower": ci[0],
            "ci_upper": ci[1],
            "confidence": config.confidence_level,
        }

    return results
```

#### Deflated Sharpe Ratio

```python
def deflated_sharpe_ratio(
    sharpe_observed: float,
    n_strategies_tested: int,
    variance_of_sharpe: float,
    skewness: float = 0,
    kurtosis: float = 3,
    n_observations: int = 252,
) -> float:
    """
    Account for multiple testing bias in Sharpe ratio selection.

    From: Bailey & López de Prado (2014)
    "The Deflated Sharpe Ratio: Correcting for Selection Bias"

    Args:
        sharpe_observed: The reported Sharpe ratio
        n_strategies_tested: Number of strategy variants tested (be honest!)
        variance_of_sharpe: Variance in Sharpe across strategies

    Returns:
        Deflated Sharpe ratio accounting for selection bias
    """
    from scipy.stats import norm

    # Expected max Sharpe under null
    e_max_sharpe = variance_of_sharpe * (
        (1 - np.euler_gamma) * norm.ppf(1 - 1/n_strategies_tested) +
        np.euler_gamma * norm.ppf(1 - 1/(n_strategies_tested * np.e))
    )

    # Deflate
    dsr = norm.cdf(
        (sharpe_observed - e_max_sharpe) /
        np.sqrt(variance_of_sharpe / n_observations)
    )

    return dsr
```

#### Complete Validation Pipeline

```python
def full_quantitative_validation(
    strategy_results: BacktestResults,
    prices: pd.DataFrame,
    config: dict,
) -> dict:
    """
    Run complete quantitative validation suite.

    Steps:
    1. Walk-forward analysis
    2. Monte Carlo permutation test
    3. Regime-conditional analysis
    4. Bootstrap confidence intervals
    5. Deflated Sharpe ratio
    6. Stationarity tests (for stat arb)
    """
    validation_report = {}

    # 1. Walk-forward
    wf_results = run_walk_forward(strategy_results, config["walk_forward"])
    validation_report["walk_forward"] = {
        "wfe": wf_results.walk_forward_efficiency,
        "oos_sharpe_mean": wf_results.oos_sharpe_mean,
        "parameter_stability": wf_results.parameter_stability,
        "passed": wf_results.wfe > config["walk_forward"]["wfe_target"],
    }

    # 2. Monte Carlo
    mc_results = monte_carlo_validation(strategy_results, config["monte_carlo"])
    validation_report["monte_carlo"] = mc_results

    # 3. Regime analysis
    regimes = detect_market_regime(prices, config["regime_detection"])
    regime_performance = analyze_by_regime(strategy_results, regimes)
    validation_report["regime_analysis"] = regime_performance

    # 4. Bootstrap CIs
    bootstrap_results = bootstrap_confidence_intervals(
        strategy_results.returns,
        config["bootstrap"]
    )
    validation_report["confidence_intervals"] = bootstrap_results

    # 5. Deflated Sharpe
    dsr = deflated_sharpe_ratio(
        sharpe_observed=strategy_results.sharpe_ratio,
        n_strategies_tested=config["n_strategies_tested"],
        variance_of_sharpe=config["variance_of_sharpe"],
    )
    validation_report["deflated_sharpe"] = {
        "raw_sharpe": strategy_results.sharpe_ratio,
        "deflated_sharpe": dsr,
        "n_strategies_tested": config["n_strategies_tested"],
    }

    # Overall pass/fail
    validation_report["passed"] = all([
        validation_report["walk_forward"]["passed"],
        validation_report["monte_carlo"]["is_significant"],
        dsr > 0.5,
        bootstrap_results["sharpe"]["ci_lower"] > 0,
    ])

    return validation_report
```

---

### 8. DEPLOYMENT.md - Live Trading & Operations

#### Deployment Progression (Updated with Shadow Mode)

```
Backtest → Dry-Run → Shadow → Paper (Testnet) → Mainnet (small) → Mainnet (full)
```

| Stage | Data | Orders | Execution | Duration | Gate Criteria |
|-------|------|--------|-----------|----------|---------------|
| Backtest | Historical | Simulated | Simulated | N/A | Sharpe > 1.0, DD < 20% |
| Dry-run | Live | Simulated | Simulated | 1 week | Consistent with backtest |
| **Shadow** | Live | Logged only | None | 2 weeks | Order quality verification |
| Paper | Live | Real (testnet) | Testnet | 2 weeks | No API errors, reconciliation OK |
| Mainnet (small) | Live | Real | Real (10% size) | 1 month | PnL positive, within risk limits |
| Mainnet (full) | Live | Real | Real (full size) | Ongoing | Production monitoring |

#### Shadow Mode (NEW)

Shadow mode submits orders to a logging system without hitting the exchange. This validates:
- Order generation timing and frequency
- Order sizing and risk limits
- Slippage estimation vs actual market moves

```python
# Shadow mode configuration
shadow_config = TradingNodeConfig(
    trader_id="SHADOW-001",
    exec_engine=ShadowExecEngineConfig(
        log_orders=True,
        execute_orders=False,  # Orders logged but not sent
        log_file="logs/shadow_orders.jsonl",
        estimate_fills=True,   # Estimate what fills would have been
    ),
)
```

#### Circuit Breaker Specification (NEW)

```python
class CircuitBreakerConfig:
    # PnL limits
    max_daily_loss_pct: float = 5.0         # Halt if daily loss exceeds
    max_drawdown_pct: float = 10.0          # Halt if DD from peak exceeds
    max_loss_per_trade_pct: float = 1.0     # Reject trades risking more

    # Order rate limits
    max_orders_per_minute: int = 100        # Runaway algo protection
    max_position_turnover: float = 10.0     # Max position * turnover per hour

    # Connectivity
    connectivity_timeout_sec: int = 30      # Flatten if disconnected
    heartbeat_interval_sec: int = 5         # Healthcheck frequency

    # Volatility
    volatility_pause_threshold: float = 10.0  # Pause if 10% move in hour
    volatility_resume_threshold: float = 5.0  # Resume when vol subsides

    # Actions
    on_trigger: str = "flatten_and_halt"    # flatten_and_halt, halt_only, alert_only
    manual_override_enabled: bool = True    # Allow manual override via API
    cooldown_period_minutes: int = 30       # Wait before auto-resume

# Circuit breaker triggers
CIRCUIT_BREAKER_TRIGGERS = {
    "daily_loss": lambda state: state.daily_pnl_pct < -config.max_daily_loss_pct,
    "drawdown": lambda state: state.drawdown_pct > config.max_drawdown_pct,
    "order_rate": lambda state: state.orders_last_minute > config.max_orders_per_minute,
    "disconnect": lambda state: state.seconds_since_heartbeat > config.connectivity_timeout_sec,
    "volatility": lambda state: state.hourly_move_pct > config.volatility_pause_threshold,
}
```

#### Live Node Architecture
```python
node = TradingNode(config=TradingNodeConfig(
    trader_id="TRADER-001",
    instance_id="INSTANCE-001",
    log_level="INFO",

    # State persistence
    cache_database=CacheDatabaseConfig(
        type="redis",
        host="localhost",
        port=6379,
    ),

    # Data engine
    data_engine=LiveDataEngineConfig(
        time_bars_build_with_no_updates=True,
    ),

    # Execution engine
    exec_engine=LiveExecEngineConfig(
        reconciliation=True,
        reconciliation_lookback_mins=1440,
    ),
))

# Multi-venue setup
node.add_data_client(BinanceDataClientConfig(...))
node.add_exec_client(BinanceExecClientConfig(...))
node.add_data_client(BybitDataClientConfig(...))
node.add_exec_client(BybitExecClientConfig(...))
node.add_data_client(OKXDataClientConfig(...))
node.add_exec_client(OKXExecClientConfig(...))
node.add_data_client(DYDXDataClientConfig(...))
node.add_exec_client(DYDXExecClientConfig(...))

node.add_strategy(MyStrategy(config))
node.run()
```

#### Disaster Recovery Plan (NEW)

```yaml
# Disaster Recovery Configuration
disaster_recovery:
  # Recovery time objectives
  rto_minutes: 15                    # Target: trading resumed in 15 min
  rpo_minutes: 1                     # Target: max 1 min data loss

  # Backup strategy
  redis_backup:
    frequency: "hourly"
    retention_days: 30
    type: "rdb_and_aof"
    offsite_location: "s3://backups/nautilus/"

  config_backup:
    frequency: "on_change"
    version_control: true
    encryption: "aes-256"

  # Recovery procedures
  scenarios:
    node_crash:
      1. "Check last known state in Redis"
      2. "Verify exchange positions via API"
      3. "Reconcile local vs exchange state"
      4. "Restart node with reconciliation=True"
      5. "Verify positions match"
      6. "Resume trading"

    redis_failure:
      1. "Start fresh Redis instance"
      2. "Restore from latest backup"
      3. "Full reconciliation with exchanges"
      4. "Verify state consistency"
      5. "Resume trading"

    exchange_api_outage:
      1. "Circuit breaker auto-triggers"
      2. "Log positions at time of outage"
      3. "Monitor exchange status page"
      4. "Upon recovery: full reconciliation"
      5. "Verify fills during outage"
      6. "Resume trading"

  # Hot standby (optional)
  hot_standby:
    enabled: false
    secondary_region: "us-west-2"
    failover_trigger: "primary_unreachable_5min"
```

#### Monitoring Infrastructure (NEW)

```yaml
# Prometheus metrics exposed by NautilusTrader
monitoring:
  prometheus:
    port: 9090
    metrics:
      - nautilus_pnl_total
      - nautilus_position_size
      - nautilus_order_count
      - nautilus_fill_latency_ms
      - nautilus_data_latency_ms
      - nautilus_errors_total

  grafana:
    dashboards:
      - trading_overview       # PnL, positions, orders
      - execution_quality      # Latency, slippage, fills
      - risk_monitor           # Drawdown, exposure, limits
      - system_health          # CPU, memory, connectivity

  alerting:
    channels:
      - slack: "#trading-alerts"
      - pagerduty: "trading-oncall"

    rules:
      - name: "Daily loss limit warning"
        condition: "nautilus_daily_pnl < -3%"
        severity: "warning"

      - name: "Daily loss limit critical"
        condition: "nautilus_daily_pnl < -5%"
        severity: "critical"
        action: "circuit_breaker_triggered"

      - name: "Connectivity lost"
        condition: "nautilus_heartbeat_age > 30s"
        severity: "critical"
        action: "page_oncall"
```

#### Operational Checklist

| Phase | Checks |
|-------|--------|
| **Pre-launch** | API connectivity ✓, balance verification ✓, position reconciliation ✓, secrets audit ✓, IP whitelist verified ✓, circuit breaker configured ✓, monitoring active ✓ |
| **Runtime** | Heartbeat monitoring ✓, PnL alerts ✓, position limits ✓, latency monitoring ✓, error rate tracking ✓ |
| **Shutdown** | Graceful stop ✓, cancel all orders ✓, flatten optional, state backup ✓ |
| **Recovery** | State reload from Redis ✓, position sync with exchange ✓, reconciliation report ✓ |

---

## Implementation Plan

### Phase 1: Foundation
1. Create Makefile with all 42 targets
2. Create docs/README.md navigation hub
3. Create docs/SETUP.md
4. Create docs/SECURITY.md

### Phase 2: Configuration & Data
5. Create docs/CONFIGURATION.md
6. Create docs/DATA_INGESTION.md

### Phase 3: Strategy & Testing
7. Create docs/STRATEGY_DEVELOPMENT.md
8. Create docs/BACKTESTING.md
9. Create docs/QUANTITATIVE_VALIDATION.md

### Phase 4: Production
10. Create docs/DEPLOYMENT.md

### Validation
Each phase validated by:
- critical-reviewer agent
- requirements-validator agent
- quant-analyst agent

---

## Success Criteria

1. ✅ All 42 Makefile targets functional
2. ✅ Documentation covers all user requirements
3. ✅ Walk-forward analysis with full specification (objective, stability, WFE)
4. ✅ Dry-run and Shadow modes clearly explained
5. ✅ Multi-exchange setup (Binance, Bybit, OKX, dYdX) covered
6. ✅ All three strategy types (trend, MM, arb) have complete templates
7. ✅ Security: Secrets management, IP whitelisting, dYdX key handling
8. ✅ Quant rigor: Monte Carlo, regime detection, bootstrap CIs, deflated Sharpe
9. ✅ Operations: Circuit breakers, disaster recovery, monitoring
10. ✅ Exchange-specific simulation parameters documented

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| v1.0 | 2026-01-29 | Initial design |
| v2.0 | 2026-01-29 | Addressed critical-reviewer, requirements-validator, quant-analyst feedback: added SECURITY.md, QUANTITATIVE_VALIDATION.md, circuit breakers, DR plan, shadow mode, complete MM/stat arb specs, Monte Carlo validation |
