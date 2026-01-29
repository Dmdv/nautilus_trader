# Setup Guide

This guide covers installing NautilusTrader for development and production use.

---

## Prerequisites

### Required

| Component | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.13+ | Runtime |
| **Rust** | Latest stable | Core compilation (source builds) |
| **clang** | 14+ | C compiler |
| **cmake** | 3.20+ | Build system |

### Recommended

| Component | Version | Purpose |
|-----------|---------|---------|
| **uv** | Latest | Fast package manager |
| **Redis** | 7.0+ | Production state management |
| **Docker** | 24+ | Containerized deployment |

---

## Quick Environment Check

```bash
make env-check
```

This verifies:
- Python version
- Rust toolchain
- Package managers
- Redis connectivity
- NautilusTrader installation

---

## Installation Methods

### Method 1: Binary Wheel (Recommended for Getting Started)

Fastest installation using pre-built wheels:

```bash
# Using uv (recommended)
uv pip install nautilus_trader

# Or using pip
pip install nautilus_trader
```

**Pros**: Fast, no compilation needed
**Cons**: Cannot modify core code, standard precision only

### Method 2: Source Release Build

For production deployments with optimizations:

```bash
make install
```

Or manually:

```bash
# Clone NautilusTrader
git clone https://github.com/nautechsystems/nautilus_trader.git
cd nautilus_trader

# Install with optimizations
poetry install
poetry build
```

**Pros**: Optimized for your CPU, full control
**Cons**: Requires Rust toolchain, slower installation

### Method 3: Source Debug Build

For development and debugging:

```bash
make install-debug
```

**Pros**: Debug symbols, better error messages
**Cons**: Slower execution, larger binaries

### Method 4: High-Precision Build

For DeFi or perpetuals requiring extreme precision:

```bash
make install-highprec
```

This enables 128-bit decimal arithmetic (vs standard 64-bit).

**When to use**:
- dYdX or other DeFi protocols
- High-leverage perpetuals
- Strategies sensitive to rounding errors

**Performance impact**: ~10-20% slower due to wider decimals

---

## Installing Prerequisites

### macOS

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.13 cmake pkg-config

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Install uv (fast package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Redis (optional, for production)
brew install redis
brew services start redis
```

### Ubuntu/Debian

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install Python 3.13
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.13 python3.13-venv python3.13-dev

# Install build tools
sudo apt install -y build-essential cmake pkg-config clang

# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Redis
sudo apt install redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

### Windows (WSL2 Recommended)

NautilusTrader is best run on Linux. For Windows, use WSL2:

```powershell
# Install WSL2 with Ubuntu
wsl --install -d Ubuntu

# Then follow Ubuntu instructions above
```

---

## Resource Requirements

| Mode | CPU | RAM | Disk | Network |
|------|-----|-----|------|---------|
| **Development** | 2 cores | 4GB | 10GB | None |
| **Backtest (small)** | 2 cores | 4GB | 10GB | None |
| **Backtest (large)** | 8+ cores | 32GB | 500GB+ | None |
| **Dry-run** | 2 cores | 4GB | 10GB | 100Mbps |
| **Paper trading** | 4 cores | 8GB | 50GB | 100Mbps |
| **Production** | 8+ cores | 16GB+ | 100GB+ | 1Gbps |

### Storage Estimates

| Data Type | Per Instrument/Day | 1 Year |
|-----------|-------------------|--------|
| 1m bars | ~100KB | ~36MB |
| Trade ticks | ~50MB | ~18GB |
| Quote ticks | ~100MB | ~36GB |
| L2 order book | ~500MB | ~180GB |

---

## Verification

After installation, verify everything works:

```python
# Test import
import nautilus_trader
print(f"NautilusTrader version: {nautilus_trader.__version__}")

# Test core components
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.identifiers import InstrumentId

print("✓ All imports successful")
```

Or use the Makefile:

```bash
make env-check
```

---

## Development Setup

For contributing or modifying strategies:

```bash
# Install with development dependencies
make install-dev

# This installs:
# - pytest, pytest-asyncio (testing)
# - mypy (type checking)
# - ruff (linting)
# - pytest-benchmark (performance testing)

# Verify development tools
make lint
make typecheck
make test
```

---

## Virtual Environment

It's recommended to use a virtual environment:

```bash
# Create venv with uv
uv venv .venv --python 3.13

# Activate
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows

# Install NautilusTrader
uv pip install nautilus_trader
```

---

## Troubleshooting

### Rust Compilation Errors

```bash
# Update Rust
rustup update stable

# Clean and rebuild
cargo clean
make clean
make install
```

### Missing Python Headers

```bash
# Ubuntu/Debian
sudo apt install python3.13-dev

# macOS
brew reinstall python@3.13
```

### Redis Connection Failed

```bash
# Check if Redis is running
redis-cli ping

# Start Redis
# macOS
brew services start redis

# Linux
sudo systemctl start redis-server
```

### Permission Errors

```bash
# Don't use sudo with pip/uv
# Instead, use a virtual environment
uv venv .venv
source .venv/bin/activate
```

### Import Errors After Installation

```bash
# Ensure you're in the right environment
which python
python -c "import nautilus_trader; print(nautilus_trader.__file__)"

# Reinstall if needed
pip uninstall nautilus_trader
make install
```

---

## Next Steps

1. **Configure credentials**: [SECURITY.md](SECURITY.md)
2. **Set up exchanges**: [CONFIGURATION.md](CONFIGURATION.md)
3. **Download data**: [DATA_INGESTION.md](DATA_INGESTION.md)
4. **Build your first strategy**: [STRATEGY_DEVELOPMENT.md](STRATEGY_DEVELOPMENT.md)
