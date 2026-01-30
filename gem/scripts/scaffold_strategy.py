import argparse
import os

TEMPLATE = """from nautilus_trader.trading.strategy import Strategy
from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.data import Bar
from nautilus_trader.model.enums import BarType

class {class_name}Config(StrategyConfig, frozen=True):
    instrument_id: str
    bar_type: str

class {class_name}(Strategy):
    def __init__(self, config: {class_name}Config):
        super().__init__(config)
        self.instrument_id = InstrumentId.from_str(config.instrument_id)

    def on_start(self):
        self.subscribe_bars(BarType.from_str(self.config.bar_type))
        self.log.info("{class_name} started")

    def on_bar(self, bar: Bar):
        self.log.info(f"Bar received: {{bar}}")

    def on_stop(self):
        self.cancel_all_orders(self.instrument_id)
        self.close_all_positions(self.instrument_id)
"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True, help="Strategy name (snake_case)")
    parser.add_argument("--type", required=True, help="Strategy type (trend, market_making, arb)")
    args = parser.parse_args()
    
    class_name = "".join(x.title() for x in args.name.split("_")) + "Strategy"
    content = TEMPLATE.format(class_name=class_name)
    
    dir_path = f"strategies/{args.type}"
    os.makedirs(dir_path, exist_ok=True)
    
    path = f"{dir_path}/{args.name}.py"
    if os.path.exists(path):
        print(f"Error: Strategy {path} already exists")
        return

    with open(path, "w") as f:
        f.write(content)
    
    # Create __init__.py if it doesn't exist
    init_path = f"{dir_path}/__init__.py"
    if not os.path.exists(init_path):
        with open(init_path, "w") as f:
            f.write("")

    print(f"Created new strategy: {path}")

if __name__ == "__main__":
    main()
