# NautilusTrader Architecture Visual Diagram

Since the Mermaid diagram generator is having browser issues, here's a detailed ASCII representation of the NautilusTrader architecture:

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                               NAUTILUS TRADER PLATFORM                             │
└─────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                EXTERNAL SYSTEMS                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   WebSocket     │  │    REST APIs    │  │  Historical     │  │     Redis       │ │
│  │     Feeds       │  │  Account/Orders │  │     Data        │  │  Cache/MsgBus   │ │
│  │ • Binance       │  │ • Binance       │  │ • Parquet       │  │ • Persistence   │ │
│  │ • Bybit         │  │ • Bybit         │  │ • PostgreSQL    │  │ • Pub/Sub       │ │
│  │ • 4OTC          │  │ • IB            │  │ • Databento     │  │ • State         │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                   DATA LAYER                                       │
│                                                                                     │
│  ┌─────────────────────────────────────────┐    ┌─────────────────────────────────┐ │
│  │            ADAPTERS (Python)            │    │      DATA PROCESSING (Rust)    │ │
│  │  ┌─────────────────┐ ┌─────────────────┐│    │  ┌─────────────────────────────┐│ │
│  │  │ Binance Adapter │ │  Bybit Adapter  ││    │  │       Data Engine           ││ │
│  │  │ • WebSocket     │ │ • WebSocket     ││────┼─▶│ • Normalization             ││ │
│  │  │ • REST          │ │ • REST          ││    │  │ • Validation                ││ │
│  │  │ • Instruments   │ │ • Instruments   ││    │  │ • Routing                   ││ │
│  │  └─────────────────┘ └─────────────────┘│    │  │ • Caching                   ││ │
│  │  ┌─────────────────┐ ┌─────────────────┐│    │  └─────────────────────────────┘│ │
│  │  │  4OTC Adapter   │ │Databento Adapter││    │  ┌─────────────────────────────┐│ │
│  │  │ • SBE Protocol  │ │ • Historical    ││    │  │      Data Client            ││ │
│  │  │ • Multi-venue   │ │ • Research      ││    │  │ • Live/Historical           ││ │
│  │  └─────────────────┘ └─────────────────┘│    │  │ • Request Management        ││ │
│  └─────────────────────────────────────────┘    │  └─────────────────────────────┘│ │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CORE ENGINE (Rust)                                    │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              MESSAGE BUS                                       │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────────┐ │ │
│  │  │  Event Routing  │  │ Topic Matching  │  │      Serialization              │ │ │
│  │  │ • Pub/Sub       │  │ • Switchboard   │  │ • Binary/JSON                   │ │ │
│  │  │ • Ordering      │  │ • Filtering     │  │ • Redis Backing                 │ │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────────────────────┘ │ │
│  └─────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────────────┐ │
│  │   CORE TYPES    │  │      CACHE      │  │         ORDER MANAGEMENT           │ │
│  │ • TradeTick     │  │ • Instruments   │  │  ┌─────────────────┐ ┌─────────────┐│ │
│  │ • QuoteTick     │  │ • Orders        │  │  │ Order Manager   │ │ Execution   ││ │
│  │ • OrderBook     │  │ • Positions     │  │  │ • Lifecycle     │ │ Manager     ││ │
│  │ • Identifiers   │  │ • Accounts      │  │  │ • Validation    │ │ • Fills     ││ │
│  │ • Price/Qty     │  │ • Performance   │  │  │ • State Mgmt    │ │ • Slippage  ││ │
│  └─────────────────┘  └─────────────────┘  │  └─────────────────┘ └─────────────┘│ │
│                                            │  ┌─────────────────────────────────┐│ │
│                                            │  │      Matching Engine            ││ │
│                                            │  │ • Simulated Exchange            ││ │
│                                            │  │ • Backtesting Engine            ││ │
│                                            │  └─────────────────────────────────┘│ │
│                                            └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           STRATEGY LAYER (Python)                                  │
│                                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────────────┐ │
│  │   STRATEGIES    │  │    ANALYSIS     │  │         RISK MANAGEMENT             │ │
│  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │  ┌─────────────────┐ ┌─────────────┐│ │
│  │ │ EMA Cross   │ │  │ │ Indicators  │ │  │  │   Risk Engine   │ │  Position   ││ │
│  │ │ Strategy    │ │  │ │ • RSI       │ │  │  │ • Position      │ │  Sizing     ││ │
│  │ └─────────────┘ │  │ │ • MACD      │ │  │  │   Limits        │ │ • Kelly     ││ │
│  │ ┌─────────────┐ │  │ │ • Bollinger │ │  │  │ • Exposure      │ │ • Fixed     ││ │
│  │ │Market Making│ │  │ │ • 50+ more  │ │  │  │ • Drawdown      │ │ • Percent   ││ │
│  │ │ Strategy    │ │  │ └─────────────┘ │  │  │ • Custom Rules  │ │ • Risk      ││ │
│  │ └─────────────┘ │  │ ┌─────────────┐ │  │  └─────────────────┘ │   Parity    ││ │
│  │ ┌─────────────┐ │  │ │Performance  │ │  │                      └─────────────┘│ │
│  │ │ Arbitrage   │ │  │ │Analytics    │ │  │                                     │ │
│  │ │ Strategy    │ │  │ │ • PnL       │ │  │                                     │ │
│  │ └─────────────┘ │  │ │ • Sharpe    │ │  │                                     │ │
│  │                 │  │ │ • Max DD    │ │  │                                     │ │
│  │                 │  │ └─────────────┘ │  │                                     │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            EXECUTION LAYER                                         │
│                                                                                     │
│  ┌─────────────────────────────────────────┐    ┌─────────────────────────────────┐ │
│  │        EXECUTION CLIENTS                │    │      ORDER PROCESSING          │ │
│  │  ┌─────────────────┐ ┌─────────────────┐│    │  ┌─────────────────────────────┐│ │
│  │  │ Binance Exec    │ │  Bybit Exec     ││    │  │     Order Emulator          ││ │
│  │  │ • Spot          │ │ • Spot          ││    │  │ • Stop Orders               ││ │
│  │  │ • Futures       │ │ • Derivatives   ││    │  │ • Limit Orders              ││ │
│  │  │ • Margin        │ │ • Options       ││    │  │ • Advanced Types            ││ │
│  │  └─────────────────┘ └─────────────────┘│    │  └─────────────────────────────┘│ │
│  │  ┌─────────────────┐ ┌─────────────────┐│    │  ┌─────────────────────────────┐│ │
│  │  │  Paper Trading  │ │   IB Execution  ││    │  │     Trailing Stops          ││ │
│  │  │ • Simulation    │ │ • Multi-Asset   ││    │  │ • Dynamic Orders            ││ │
│  │  │ • No Real Money │ │ • Global Access ││    │  │ • Algorithm Orders          ││ │
│  │  └─────────────────┘ └─────────────────┘│    │  └─────────────────────────────┘│ │
│  └─────────────────────────────────────────┘    └─────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                         CONTROL & MONITORING                                       │
│                                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────────────┐ │
│  │ Trading Node    │  │ Logging System  │  │            Metrics                  │ │
│  │ • Orchestration │  │ • Structured    │  │ • Performance Monitoring            │ │
│  │ • Lifecycle     │  │ • Multiple      │  │ • Latency Measurement               │ │
│  │ • Configuration │  │   Levels        │  │ • Throughput Analysis               │ │
│  │ • Health Checks │  │ • Audit Trail   │  │ • Resource Usage                    │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Architecture

```
DATA FLOW: External → Internal → Strategy → Execution → External

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Market    │───▶│  Adapters   │───▶│    Data     │───▶│  Message    │───▶│  Strategy   │
│    Data     │    │  (Python)   │    │   Engine    │    │     Bus     │    │   Layer     │
│ • WebSocket │    │ • Normalize │    │   (Rust)    │    │   (Rust)    │    │  (Python)   │
│ • REST      │    │ • Validate  │    │ • Cache     │    │ • Route     │    │ • Analyze   │
│ • Historical│    │ • Convert   │    │ • Process   │    │ • Publish   │    │ • Decide    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                                                                     │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────▼──────┐
│  Venue      │◀───│ Execution   │◀───│   Order     │◀───│    Risk     │◀───│   Orders    │
│   APIs      │    │  Clients    │    │  Manager    │    │   Engine    │    │ • Buy/Sell  │
│ • Place     │    │ • Binance   │    │ • Validate  │    │ • Limits    │    │ • Stop/Lmt  │
│ • Cancel    │    │ • Bybit     │    │ • Track     │    │ • Check     │    │ • Advanced  │
│ • Modify    │    │ • Paper     │    │ • Execute   │    │ • Approve   │    │ • Cancel    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## Language Distribution

```
RUST COMPONENTS (High Performance):
├── Core Data Types (Price, Quantity, TradeTick, etc.)
├── Message Bus & Serialization
├── Cache System
├── Order Management
├── Execution Engine  
├── Matching Engine
├── Risk Engine Core
└── Time-Critical Algorithms

PYTHON COMPONENTS (Developer Experience):
├── Adapters (Binance, Bybit, 4OTC, etc.)
├── Strategy Development
├── Indicators & Analytics
├── Configuration Management
├── Risk Rules & Logic  
├── Performance Analysis
└── Research & Backtesting Scripts

CYTHON COMPONENTS (Legacy/Bridge):
├── Python-Rust Bindings
├── Performance-Critical Python Extensions  
└── Legacy Components (Being Migrated to Rust)
```

## Performance Characteristics

```
LATENCY PROFILE:
┌─────────────────────┬─────────────┬─────────────┐
│ Component           │   Latency   │  Language   │
├─────────────────────┼─────────────┼─────────────┤
│ Data Ingestion      │ 10-100μs    │ Rust        │
│ Message Bus         │ 1-10μs      │ Rust        │
│ Cache Access        │ 100-500ns   │ Rust        │  
│ Strategy Logic      │ 10-100μs    │ Python      │
│ Order Processing    │ 1-10μs      │ Rust        │
│ Risk Checks         │ 1-5μs       │ Rust        │
│ Execution Submit    │ 10-100μs    │ Python      │
├─────────────────────┼─────────────┼─────────────┤
│ END-TO-END TOTAL    │ 50-500μs    │ Mixed       │
└─────────────────────┴─────────────┴─────────────┘
```

This architecture enables NautilusTrader to serve as a professional-grade algorithmic trading platform, balancing performance (Rust core) with developer productivity (Python strategies).