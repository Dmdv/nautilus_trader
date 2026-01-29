# Data Ingestion Guide

This guide covers setting up data pipelines for backtesting and live trading.

---

## Data Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Data Sources   │     │   Transformation │     │     Storage      │
├─────────────────┤     ├──────────────────┤     ├──────────────────┤
│ • Tardis        │────▶│ • Data Wranglers │────▶│ • Parquet Catalog│
│ • Exchange APIs │     │ • Type Converters│     │ • In-Memory      │
│ • CSV Files     │     │ • Normalization  │     │ • Redis Cache    │
└─────────────────┘     └──────────────────┘     └──────────────────┘
                                                          │
                                                          ▼
                                                 ┌──────────────────┐
                                                 │  Consumption     │
                                                 ├──────────────────┤
                                                 │ • BacktestEngine │
                                                 │ • BacktestNode   │
                                                 │ • Live Trading   │
                                                 └──────────────────┘
```

---

## Data Types

### Hierarchy (Most to Least Granular)

| Data Type | Granularity | Typical Size/Day | Use Case |
|-----------|-------------|------------------|----------|
| L3 Order Book (MBO) | Individual orders | 1-5 GB | HFT, market microstructure |
| L2 Order Book (MBP) | Price levels | 500 MB | Market making |
| Quote Ticks | Best bid/ask | 100 MB | Stat arb, spread analysis |
| Trade Ticks | Executed trades | 50 MB | Volume analysis, VWAP |
| Bars (OHLCV) | Time aggregated | 100 KB - 1 MB | Trend following |

### Recommended Data by Strategy

| Strategy Type | Primary Data | Secondary Data | Auxiliary |
|---------------|--------------|----------------|-----------|
| **Trend-following** | 1m-1h bars | Volume | Funding rates, OI |
| **Market Making** | L2 order book | Trade ticks | Volatility |
| **Stat Arb** | Quote ticks (multi-venue) | Trade ticks | Funding rates |
| **Cross-exchange Arb** | L2 books (both venues) | Latency samples | Transfer status |

---

## Tardis Integration

[Tardis](https://tardis.dev) provides historical crypto market data with millisecond precision.

### Setup

```bash
# Install Tardis client
pip install tardis-dev

# Set API key
export TARDIS_API_KEY=your_api_key

# Or add to .env
echo "TARDIS_API_KEY=your_api_key" >> .env
```

### Download Data

Using Makefile:

```bash
# Download with default settings
make tardis-download

# Download specific date range
make data-download-range START=2024-01-01 END=2024-12-31 SYMBOL=BTCUSDT
```

Using Python:

```python
from tardis_dev import datasets

# Download trade data
datasets.download(
    exchange="binance-futures",
    data_types=["trades"],
    from_date="2024-01-01",
    to_date="2024-12-31",
    symbols=["BTCUSDT"],
    api_key=os.environ["TARDIS_API_KEY"],
    download_dir="data/raw/tardis",
)

# Download order book snapshots (100ms intervals)
datasets.download(
    exchange="binance-futures",
    data_types=["book_snapshot_5_100ms"],  # Top 5 levels, 100ms
    from_date="2024-01-01",
    to_date="2024-12-31",
    symbols=["BTCUSDT"],
    api_key=os.environ["TARDIS_API_KEY"],
    download_dir="data/raw/tardis",
)

# Download incremental order book updates
datasets.download(
    exchange="binance-futures",
    data_types=["incremental_book_L2"],
    from_date="2024-01-01",
    to_date="2024-12-31",
    symbols=["BTCUSDT"],
    api_key=os.environ["TARDIS_API_KEY"],
    download_dir="data/raw/tardis",
)
```

### Tardis Data Types

| Type | Description | Update Frequency |
|------|-------------|------------------|
| `trades` | Executed trades | Real-time |
| `book_snapshot_5_100ms` | Top 5 levels | 100ms |
| `book_snapshot_25_100ms` | Top 25 levels | 100ms |
| `incremental_book_L2` | Level 2 deltas | Real-time |
| `quotes` | Best bid/ask | Real-time |
| `derivative_ticker` | Funding, OI | Periodic |

### Supported Exchanges

| Exchange | Tardis Name | Data Available From |
|----------|-------------|---------------------|
| Binance Futures | `binance-futures` | 2019 |
| Binance Spot | `binance` | 2017 |
| Bybit | `bybit` | 2020 |
| OKX | `okex-swap` | 2020 |
| dYdX | `dydx` | 2021 |

---

## Data Transformation

### Data Wranglers

NautilusTrader provides wranglers to convert raw data to internal objects:

```python
from nautilus_trader.persistence.wranglers import (
    TradeTickDataWrangler,
    QuoteTickDataWrangler,
    BarDataWrangler,
    OrderBookDeltaDataWrangler,
)

# For trade ticks
wrangler = TradeTickDataWrangler(instrument)
trade_ticks = wrangler.process(df)

# For quote ticks
wrangler = QuoteTickDataWrangler(instrument)
quote_ticks = wrangler.process(df)

# For bars
wrangler = BarDataWrangler(bar_type, instrument)
bars = wrangler.process(df)

# For order book deltas
wrangler = OrderBookDeltaDataWrangler(instrument)
deltas = wrangler.process(df)
```

### Tardis CSV to NautilusTrader

```python
import pandas as pd
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.persistence.wranglers import TradeTickDataWrangler

# 1. Load Tardis CSV
df = pd.read_csv(
    "data/raw/tardis/binance-futures_trades_2024-01-01_BTCUSDT.csv.gz",
    compression="gzip"
)

# 2. Create instrument
instrument = CurrencyPair(
    instrument_id=InstrumentId.from_str("BTCUSDT-PERP.BINANCE"),
    raw_symbol=Symbol("BTCUSDT"),
    base_currency=BTC,
    quote_currency=USDT,
    price_precision=2,
    size_precision=3,
    price_increment=Price.from_str("0.01"),
    size_increment=Quantity.from_str("0.001"),
    lot_size=Quantity.from_str("0.001"),
    max_quantity=Quantity.from_str("1000"),
    min_quantity=Quantity.from_str("0.001"),
    margin_init=Decimal("0.01"),
    margin_maint=Decimal("0.005"),
    maker_fee=Decimal("0.0002"),
    taker_fee=Decimal("0.0004"),
    ts_event=0,
    ts_init=0,
)

# 3. Transform with wrangler
wrangler = TradeTickDataWrangler(instrument)

# Tardis CSV columns: timestamp, symbol, side, price, amount, ...
# Wrangler expects specific column names
df_renamed = df.rename(columns={
    "timestamp": "ts_event",
    "price": "price",
    "amount": "size",
    "side": "aggressor_side",
})

trade_ticks = wrangler.process(df_renamed)
```

---

## Parquet Data Catalog

The Parquet catalog provides efficient columnar storage with automatic partitioning.

### Catalog Structure

```
data/catalog/
├── trade_tick/
│   └── BTCUSDT-PERP.BINANCE/
│       └── 2024/
│           ├── 01/
│           │   └── data.parquet
│           ├── 02/
│           │   └── data.parquet
│           └── ...
├── quote_tick/
│   └── ETHUSDT-PERP.BINANCE/
│       └── 2024/01/data.parquet
├── bar_1m/
│   └── BTCUSDT-PERP.BYBIT/
│       └── 2024/01/data.parquet
└── order_book_delta/
    └── BTC-USD.DYDX/
        └── 2024/01/data.parquet
```

### Creating a Catalog

```python
from nautilus_trader.persistence.catalog import ParquetDataCatalog

# Create catalog
catalog = ParquetDataCatalog("data/catalog")

# Write data
catalog.write_data(trade_ticks)
catalog.write_data(quote_ticks)
catalog.write_data(bars)
catalog.write_data(order_book_deltas)
```

### Reading from Catalog

```python
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.model.identifiers import InstrumentId

catalog = ParquetDataCatalog("data/catalog")

# Read trade ticks
trade_ticks = catalog.trade_ticks(
    instrument_ids=[InstrumentId.from_str("BTCUSDT-PERP.BINANCE")],
    start="2024-01-01",
    end="2024-01-31",
)

# Read bars
bars = catalog.bars(
    bar_types=[BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL")],
    start="2024-01-01",
    end="2024-01-31",
)

# Read order book deltas
deltas = catalog.order_book_deltas(
    instrument_ids=[InstrumentId.from_str("BTCUSDT-PERP.BINANCE")],
    start="2024-01-01",
    end="2024-01-31",
)
```

### Catalog Info

```bash
# Show catalog statistics
make data-catalog-info
```

Or programmatically:

```python
catalog = ParquetDataCatalog("data/catalog")

# List instruments
instruments = catalog.instruments()
for inst in instruments:
    print(f"{inst.id}: {inst.asset_class}")

# Check data range
for instrument_id in catalog.instrument_ids():
    ticks = catalog.trade_ticks(instrument_ids=[instrument_id])
    if ticks:
        print(f"{instrument_id}: {ticks[0].ts_event} to {ticks[-1].ts_event}")
```

---

## Importing Existing Data

### From CSV Files

```bash
# Import via Makefile
make data-import FILE=path/to/data.csv
```

```python
import pandas as pd
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.persistence.wranglers import BarDataWrangler

# 1. Load your CSV
df = pd.read_csv("my_data.csv")

# Expected columns for bars: timestamp, open, high, low, close, volume
# Adjust column names as needed
df = df.rename(columns={
    "time": "timestamp",
    "o": "open",
    "h": "high",
    "l": "low",
    "c": "close",
    "v": "volume",
})

# 2. Create instrument (must match your data)
instrument = create_instrument("BTCUSDT-PERP.BINANCE")

# 3. Create bar type
bar_type = BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL")

# 4. Transform
wrangler = BarDataWrangler(bar_type, instrument)
bars = wrangler.process(df)

# 5. Write to catalog
catalog = ParquetDataCatalog("data/catalog")
catalog.write_data(bars)
```

### From Other Formats

**Parquet files**:
```python
df = pd.read_parquet("data.parquet")
# Then use wrangler as above
```

**JSON files**:
```python
df = pd.read_json("data.json", lines=True)
# Then use wrangler as above
```

**Database**:
```python
import sqlalchemy
engine = sqlalchemy.create_engine("postgresql://...")
df = pd.read_sql("SELECT * FROM trades", engine)
# Then use wrangler as above
```

---

## Data Validation

### Check Data Integrity

```bash
make data-validate
```

### Validation Checks

```python
def validate_trade_ticks(ticks: list) -> dict:
    """Validate trade tick data quality."""
    issues = []

    # Check timestamps are ascending
    for i in range(1, len(ticks)):
        if ticks[i].ts_event < ticks[i-1].ts_event:
            issues.append(f"Timestamp out of order at index {i}")

    # Check for gaps (> 1 hour without trades is suspicious for BTC)
    for i in range(1, len(ticks)):
        gap = ticks[i].ts_event - ticks[i-1].ts_event
        if gap > 3600 * 1e9:  # 1 hour in nanoseconds
            issues.append(f"Gap of {gap/1e9/3600:.1f} hours at index {i}")

    # Check for invalid prices
    for i, tick in enumerate(ticks):
        if tick.price.as_double() <= 0:
            issues.append(f"Invalid price at index {i}: {tick.price}")

    # Check for invalid sizes
    for i, tick in enumerate(ticks):
        if tick.size.as_double() <= 0:
            issues.append(f"Invalid size at index {i}: {tick.size}")

    return {
        "total_ticks": len(ticks),
        "issues": issues,
        "is_valid": len(issues) == 0,
    }
```

### Gap Detection

```python
def find_data_gaps(catalog, instrument_id, bar_type, expected_bars_per_day=1440):
    """Find missing data periods."""
    bars = catalog.bars(bar_types=[bar_type])

    gaps = []
    for i in range(1, len(bars)):
        expected_gap = 60 * 1e9  # 1 minute in nanoseconds
        actual_gap = bars[i].ts_event - bars[i-1].ts_event

        if actual_gap > expected_gap * 2:  # More than 2x expected
            gaps.append({
                "start": bars[i-1].ts_event,
                "end": bars[i].ts_event,
                "missing_bars": int(actual_gap / expected_gap) - 1,
            })

    return gaps
```

---

## Storage Estimates

### By Data Type

| Data Type | Size/Instrument/Day | 1 Year | 5 Years |
|-----------|---------------------|--------|---------|
| 1m bars | ~100 KB | ~36 MB | ~180 MB |
| 5m bars | ~20 KB | ~7 MB | ~35 MB |
| Trade ticks | ~50 MB | ~18 GB | ~90 GB |
| Quote ticks | ~100 MB | ~36 GB | ~180 GB |
| L2 order book (100ms) | ~500 MB | ~180 GB | ~900 GB |

### By Strategy Type

| Strategy | Instruments | Data Type | 1 Year Storage |
|----------|-------------|-----------|----------------|
| Trend (single) | 1 | 1m bars | ~36 MB |
| Trend (multi) | 10 | 1m bars | ~360 MB |
| Market making | 1 | L2 book | ~180 GB |
| Stat arb (pairs) | 2 | Quote ticks | ~72 GB |
| Cross-exchange | 2 | L2 book | ~360 GB |

### Compression

Parquet provides ~70-80% compression:

| Raw Size | Parquet Size |
|----------|--------------|
| 1 GB | ~200-300 MB |
| 10 GB | ~2-3 GB |
| 100 GB | ~20-30 GB |

---

## Live Data Feeds

### Subscribing to Live Data

```python
from nautilus_trader.model.data import BarType, BookType

class MyStrategy(Strategy):
    def on_start(self):
        # Subscribe to bars
        bar_type = BarType.from_str("BTCUSDT-PERP.BINANCE-1-MINUTE-LAST-EXTERNAL")
        self.subscribe_bars(bar_type)

        # Subscribe to trade ticks
        self.subscribe_trade_ticks(self.instrument_id)

        # Subscribe to quote ticks
        self.subscribe_quote_ticks(self.instrument_id)

        # Subscribe to order book (L2)
        self.subscribe_order_book_deltas(
            instrument_id=self.instrument_id,
            book_type=BookType.L2_MBP,
            depth=10,  # Top 10 levels
        )

    def on_bar(self, bar: Bar):
        # Process bar data
        pass

    def on_trade_tick(self, tick: TradeTick):
        # Process trade tick
        pass

    def on_quote_tick(self, tick: QuoteTick):
        # Process quote tick
        pass

    def on_order_book_deltas(self, deltas: OrderBookDeltas):
        # Process order book updates
        pass
```

### Data Latency

| Exchange | WebSocket Latency | REST Latency |
|----------|-------------------|--------------|
| Binance | 10-50ms | 50-100ms |
| Bybit | 10-50ms | 50-100ms |
| OKX | 10-50ms | 50-100ms |
| dYdX | 100-300ms | 200-500ms |

---

## Troubleshooting

### Common Issues

**Empty catalog query**:
```
Problem: catalog.trade_ticks() returns empty list
Solutions:
1. Check instrument_id matches exactly (case-sensitive)
2. Verify date range overlaps with data
3. Check data was written with correct instrument
```

**Memory errors with large data**:
```
Problem: Out of memory when loading data
Solutions:
1. Use BacktestNode instead of BacktestEngine (streams data)
2. Reduce date range
3. Use bars instead of ticks
4. Increase system memory
```

**Timestamp parsing errors**:
```
Problem: "Cannot parse timestamp" error
Solutions:
1. Ensure timestamps are in nanoseconds (Unix epoch)
2. Convert: ts_ns = int(pd.Timestamp(ts).timestamp() * 1e9)
3. Check timezone (should be UTC)
```

**Data gaps causing issues**:
```
Problem: Strategy errors due to missing data
Solutions:
1. Run make data-validate to identify gaps
2. Fill gaps with Tardis download
3. Handle gaps in strategy code
```

---

## Best Practices

1. **Start with bars** - Easier to work with, lower storage requirements
2. **Validate before backtesting** - Run `make data-validate` first
3. **Use appropriate granularity** - Don't use tick data for daily strategies
4. **Partition by time** - The catalog handles this automatically
5. **Compress old data** - Parquet handles compression automatically
6. **Document data sources** - Track where data came from and any transformations
7. **Version your catalog** - Tag or snapshot before major changes

---

## Next Steps

1. **Configure exchanges**: [CONFIGURATION.md](CONFIGURATION.md)
2. **Build strategies**: [STRATEGY_DEVELOPMENT.md](STRATEGY_DEVELOPMENT.md)
3. **Run backtests**: [BACKTESTING.md](BACKTESTING.md)
