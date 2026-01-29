# NautilusTrader Documentation

> High-performance algorithmic trading framework for crypto markets

This documentation covers setup, configuration, strategy development, backtesting, and production deployment for NautilusTrader focused on **Binance, Bybit, OKX, and dYdX** exchanges.

---

## Quick Start

```bash
# 1. Check prerequisites
make env-check

# 2. Install NautilusTrader
make install

# 3. Generate config template
make config-template

# 4. Copy and fill in your API keys
cp .env.template .env
# Edit .env with your credentials

# 5. Verify configuration
make config-check

# 6. Run your first backtest
make backtest-run CONFIG=config/example_backtest.yaml
```

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [SETUP.md](SETUP.md) | Installation, prerequisites, build options |
| [SECURITY.md](SECURITY.md) | Secrets management, IP whitelisting, credential handling |
| [CONFIGURATION.md](CONFIGURATION.md) | Exchange configuration, Redis, tuning parameters |
| [DATA_INGESTION.md](DATA_INGESTION.md) | Tardis integration, Parquet catalog, data imports |
| [STRATEGY_DEVELOPMENT.md](STRATEGY_DEVELOPMENT.md) | Strategy patterns for trend, market making, stat arb |
| [BACKTESTING.md](BACKTESTING.md) | BacktestEngine, BacktestNode, walk-forward analysis |
| [QUANTITATIVE_VALIDATION.md](QUANTITATIVE_VALIDATION.md) | Monte Carlo, regime detection, bootstrap CIs |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Dry-run, shadow, paper, production deployment |

---

## Deployment Progression

```
┌──────────┐    ┌─────────┐    ┌────────┐    ┌───────┐    ┌─────────────┐    ┌─────────────┐
│ Backtest │───▶│ Dry-Run │───▶│ Shadow │───▶│ Paper │───▶│ Mainnet 10% │───▶│ Mainnet 100%│
└──────────┘    └─────────┘    └────────┘    └───────┘    └─────────────┘    └─────────────┘
 Historical      Live data      Orders        Testnet      Real money        Full size
 Simulated       Simulated      Logged        Real orders  Small positions   Production
```

| Stage | Data | Execution | Command |
|-------|------|-----------|---------|
| Backtest | Historical | Simulated | `make backtest-run` |
| Dry-run | Live | Simulated | `make dry-run` |
| Shadow | Live | Logged only | `make shadow-run` |
| Paper | Live | Testnet | `make live-paper` |
| Production | Live | Mainnet | `make live-prod` |

---

## Makefile Targets Overview

### Setup
```bash
make install          # Install release build
make install-debug    # Install with debug symbols
make install-dev      # Install with dev dependencies
make env-check        # Verify environment
make clean            # Remove build artifacts
```

### Testing
```bash
make test             # Run all tests
make test-unit        # Unit tests only
make lint             # Run linters
make typecheck        # Type checking
```

### Security
```bash
make secrets-check    # Audit for exposed secrets
make security-audit   # Full security audit
make ip-whitelist-verify  # Check IP whitelisting
```

### Data
```bash
make tardis-download  # Download from Tardis
make data-import      # Import existing data
make data-catalog-info # Show catalog stats
make data-validate    # Check data integrity
```

### Strategy
```bash
make strategy-new NAME=my_strat TYPE=trend  # Scaffold new strategy
make strategy-test    # Test strategies
make strategy-validate CONFIG=...  # Validate config
```

### Backtesting
```bash
make backtest-run CONFIG=...      # Run backtest
make backtest-walkforward CONFIG=...  # Walk-forward analysis
make backtest-montecarlo RESULTS=...  # Monte Carlo validation
make backtest-report RESULTS=...  # Generate report
```

### Live Trading
```bash
make dry-run CONFIG=...   # Live data, simulated execution
make shadow-run CONFIG=...# Orders logged, not submitted
make live-paper CONFIG=...# Paper trading (testnet)
make live-prod CONFIG=... # Production (requires confirmation)
make live-stop            # Graceful shutdown
```

### Operations
```bash
make health-check     # System health
make backup-state     # Backup Redis and configs
make logs-tail        # Tail logs
make exchange-status  # Check exchange connectivity
```

---

## Supported Exchanges

| Exchange | Spot | Futures | Status |
|----------|------|---------|--------|
| Binance | ✅ | ✅ | Stable |
| Bybit | ✅ | ✅ | Stable |
| OKX | ✅ | ✅ | Stable |
| dYdX | - | ✅ | Stable |

---

## Strategy Types

### Trend-Following
- EMA/SMA crossovers
- Breakout detection
- Momentum indicators

### Market Making
- Avellaneda-Stoikov framework
- Inventory-based quote skewing
- VPIN adverse selection detection

### Statistical Arbitrage
- Johansen cointegration testing
- Kalman filter hedge ratios
- Ornstein-Uhlenbeck half-life estimation

---

## Project Structure

```
nautilius_trader2/
├── config/                 # Configuration files
│   ├── backtest/          # Backtest configs
│   ├── live/              # Live trading configs
│   └── strategies/        # Strategy configs
├── data/
│   ├── catalog/           # Parquet data catalog
│   └── raw/               # Raw data downloads
├── docs/                  # Documentation
│   ├── plans/             # Design documents
│   └── *.md               # User guides
├── logs/                  # Trading logs
├── results/               # Backtest results
├── scripts/               # Utility scripts
├── strategies/            # Custom strategies
│   ├── trend/
│   ├── market_making/
│   └── arb/
├── tests/                 # Test suite
├── .env                   # Environment variables (not committed)
├── .env.template          # Template for .env
├── Makefile               # 42 development targets
└── README.md              # This file
```

---

## Requirements

- **Python**: 3.13+
- **Rust**: Latest stable (for source builds)
- **Redis**: 7.0+ (for production state management)
- **OS**: Linux (production), macOS (development)

---

## Security

⚠️ **Critical**: Read [SECURITY.md](SECURITY.md) before deploying to production.

Key points:
- Never store mnemonics in plaintext for production
- Use HashiCorp Vault or AWS KMS for secrets
- Enable IP whitelisting on all exchanges
- Separate read-only and trade API keys

---

## Support

- **NautilusTrader Docs**: https://nautilustrader.io/docs
- **GitHub Issues**: https://github.com/nautechsystems/nautilus_trader/issues
- **Discord**: https://discord.gg/nautilus

---

## License

This project uses NautilusTrader which is licensed under LGPL-3.0.
