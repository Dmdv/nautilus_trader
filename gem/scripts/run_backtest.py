import argparse
import sys
from scripts.utils.config_loader import load_config
from nautilus_trader.backtest.node import BacktestNode, BacktestVenueConfig, BacktestDataConfig, BacktestRunConfig, BacktestEngineConfig
from nautilus_trader.config import ImportableStrategyConfig

def parse_backtest_config(config_path: str) -> BacktestRunConfig:
    raw_config = load_config(config_path)
    
    # Parse Venues
    venues = []
    for v in raw_config['venues']:
        venues.append(BacktestVenueConfig(
            name=v['name'],
            oms_type=v['oms_type'],
            account_type=v['account_type'],
            starting_balances=[v['starting_balances'][0]] # Simplified
        ))
    
    # Parse Data
    data = []
    for d in raw_config['data']:
        data.append(BacktestDataConfig(
            catalog_path=d['catalog_path'],
            data_cls=d['data_cls'],
            instrument_id=d['instrument_id'],
            bar_spec=d.get('bar_spec'),
            start_time=d.get('start_time'),
            end_time=d.get('end_time'),
        ))

    # Parse Strategies
    strategies = []
    for s in raw_config['strategies']:
        strategies.append(ImportableStrategyConfig(
            strategy_path=s['strategy_path'],
            config_path=s['config_path'],
            config=s['config'],
        ))

    return BacktestRunConfig(
        engine=BacktestEngineConfig(
            trader_id=raw_config.get('trader_id', 'BACKTESTER'),
            strategies=strategies,
        ),
        venues=venues,
        data=data,
    )

def main():
    parser = argparse.ArgumentParser(description="Run backtest")
    parser.add_argument("--config", required=True, help="Path to config file")
    args = parser.parse_args()
    
    try:
        print(f"Loading config from {args.config}...")
        run_config = parse_backtest_config(args.config)
        
        print("Initializing BacktestNode...")
        node = BacktestNode(configs=[run_config])
        
        print("Running backtest...")
        node.run()
        
        print("\nBacktest Complete.")
        # print(results) # Print summary if available
        
    except Exception as e:
        print(f"Error running backtest: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()