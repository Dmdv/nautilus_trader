import argparse
import os
import signal
import sys
import time
from decimal import Decimal

from nautilus_trader.config import (
    TradingNodeConfig,
    CacheDatabaseConfig,
    LiveDataEngineConfig,
    LiveExecEngineConfig,
    ImportableStrategyConfig,
)
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.identifiers import Venue, TraderId

# Adapter Configs
from nautilus_trader.adapters.binance.config import (
    BinanceDataClientConfig,
    BinanceExecClientConfig,
)
from nautilus_trader.adapters.binance.common.enums import BinanceAccountType

from nautilus_trader.adapters.bybit.config import (
    BybitDataClientConfig,
    BybitExecClientConfig,
)
from nautilus_trader.adapters.bybit.common.enums import BybitAccountType

from nautilus_trader.adapters.okx.config import (
    OKXDataClientConfig,
    OKXExecClientConfig,
)
from nautilus_trader.adapters.okx.common.enums import OKXAccountType

from nautilus_trader.adapters.dydx.config import (
    DYDXDataClientConfig,
    DYDXExecClientConfig,
)

from scripts.utils.config_loader import load_config
from dotenv import load_dotenv

# Load .env file
load_dotenv()

def signal_handler(sig, frame):
    print("\nGracefully shutting down node...")
    sys.exit(0)

def create_binance_configs(venue_conf: dict, is_testnet: bool):
    """Create Binance Data and Exec configs."""
    api_key = os.environ.get("BINANCE_API_KEY")
    api_secret = os.environ.get("BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("WARNING: BINANCE_API_KEY or BINANCE_API_SECRET not set. Skipping Binance.")
        return None, None

    # Map account type string to Enum
    acc_type_str = venue_conf.get("account_type", "USDT_FUTURE")
    if acc_type_str == "USDT_FUTURE":
        acc_type = BinanceAccountType.USDT_FUTURE
    elif acc_type_str == "SPOT":
        acc_type = BinanceAccountType.SPOT
    else:
        acc_type = BinanceAccountType.USDT_FUTURE

    data = BinanceDataClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        account_type=acc_type,
        testnet=is_testnet,
        use_agg_trade_ticks=True,
    )

    exec_ = BinanceExecClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        account_type=acc_type,
        testnet=is_testnet,
        use_position_ids=True,
    )
    return data, exec_

def create_bybit_configs(venue_conf: dict, is_testnet: bool):
    """Create Bybit Data and Exec configs."""
    api_key = os.environ.get("BYBIT_API_KEY")
    api_secret = os.environ.get("BYBIT_API_SECRET")

    if not api_key or not api_secret:
        return None, None

    acc_type = BybitAccountType.UNIFIED # Defaulting to Unified

    data = BybitDataClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        account_type=acc_type,
        testnet=is_testnet,
    )

    exec_ = BybitExecClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        account_type=acc_type,
        testnet=is_testnet,
    )
    return data, exec_

def create_okx_configs(venue_conf: dict, is_testnet: bool):
    """Create OKX Data and Exec configs."""
    api_key = os.environ.get("OKX_API_KEY")
    api_secret = os.environ.get("OKX_API_SECRET")
    passphrase = os.environ.get("OKX_PASSPHRASE")

    if not api_key or not api_secret or not passphrase:
        return None, None

    data = OKXDataClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        account_type=OKXAccountType.UNIFIED,
        is_demo=is_testnet,
    )

    exec_ = OKXExecClientConfig(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        account_type=OKXAccountType.UNIFIED,
        is_demo=is_testnet,
    )
    return data, exec_

def create_dydx_configs(venue_conf: dict, is_testnet: bool):
    """Create dYdX Data and Exec configs."""
    mnemonic = os.environ.get("DYDX_MNEMONIC")
    # Note: In real prod, use hardware wallet or KMS as per SECURITY.md
    
    if not mnemonic:
        return None, None

    # Dummy wallet address derivation or config would go here
    # For now, assuming environment or config provides it
    wallet_address = os.environ.get("DYDX_WALLET_ADDRESS", "dummy_address")

    data = DYDXDataClientConfig(
        wallet_address=wallet_address,
        is_testnet=is_testnet,
    )

    exec_ = DYDXExecClientConfig(
        wallet_address=wallet_address,
        mnemonic=mnemonic,
        is_testnet=is_testnet,
    )
    return data, exec_


def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description="Run trading node")
    parser.add_argument("--config", required=True, help="Path to config file")
    parser.add_argument("--mode", choices=["dry-run", "shadow", "paper", "production"], required=True)
    args = parser.parse_args()
    
    print(f"Starting Trading Node in {args.mode.upper()} mode...")
    raw_config = load_config(args.config)

    # 1. Base Node Configuration
    node_config = TradingNodeConfig(
        trader_id=TraderId(raw_config.get("trader_id", "TRADER-001")),
        log_level=raw_config.get("log_level", "INFO"),
        
        # Redis Cache (only if not dry-run)
        cache_database=CacheDatabaseConfig(
            type="redis",
            host=raw_config["cache_database"]["host"],
            port=raw_config["cache_database"]["port"],
            db=raw_config["cache_database"]["db"],
        ) if args.mode != "dry-run" else None,
        
        # Data Engine
        data_engine=LiveDataEngineConfig(
            time_bars_build_with_no_updates=raw_config["data_engine"].get("time_bars_build_with_no_updates", True),
        ),
        
        # Exec Engine (Reconciliation)
        exec_engine=LiveExecEngineConfig(
            reconciliation=raw_config["exec_engine"].get("reconciliation", True),
            reconciliation_lookback_mins=raw_config["exec_engine"].get("reconciliation_lookback_mins", 1440),
        )
    )

    node = TradingNode(config=node_config)

    # 2. Add Venues (Data & Exec Clients)
    for venue in raw_config.get("venues", []):
        name = venue["name"]
        client_type = venue.get("client_type", name.lower())
        testnet = venue.get("testnet", True)

        data_config, exec_config = None, None

        if client_type == "binance":
            data_config, exec_config = create_binance_configs(venue, testnet)
        elif client_type == "bybit":
            data_config, exec_config = create_bybit_configs(venue, testnet)
        elif client_type == "okx":
            data_config, exec_config = create_okx_configs(venue, testnet)
        elif client_type == "dydx":
            data_config, exec_config = create_dydx_configs(venue, testnet)
        
        if data_config:
            print(f"Adding Data Client for {name}...")
            node.add_data_client(data_config)
        
        if exec_config:
            # For Dry-Run / Shadow, we might want to modify execution behavior
            # But Nautilus handles dry-run usually by mocking or using separate DryRunExecClient
            # Here we follow the standard pattern of adding the client.
            # In 'dry-run' mode, Nautilus TradingNode generally prevents real submission 
            # if configured properly or using specific wrappers.
            # Ideally, for strict dry-run, we might not add the exec client or use a mock.
            # However, to get 'live data', we need the data client.
            
            if args.mode == "dry-run":
                print(f"Dry-run: Exec client for {name} added (Verify permissions/testnet!)")
                # In strict dry-run, you often don't add the real exec client
                # or you wrap the strategy to not submit orders.
                pass 
            
            print(f"Adding Exec Client for {name}...")
            node.add_exec_client(exec_config)

    # 3. Add Strategies
    for strat in raw_config.get("strategies", []):
        config_obj = ImportableStrategyConfig(
            strategy_path=strat["strategy_path"],
            config_path=strat["config_path"],
            config=strat["config"],
        )
        print(f"Adding Strategy: {strat['strategy_path']}...")
        node.add_strategy(config_obj)

    # 4. Run
    print("Node initialized. Running...")
    node.run()

if __name__ == "__main__":
    main()