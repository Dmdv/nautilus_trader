import os
import argparse
from datetime import datetime, timedelta
from tardis_dev import datasets
from dotenv import load_dotenv

load_dotenv()

def main():
    parser = argparse.ArgumentParser(description="Download data from Tardis")
    parser.add_argument("--exchange", default="binance-futures", help="Exchange name")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol (e.g., BTCUSDT)")
    # Default to last 30 days if not specified
    default_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    default_end = datetime.now().strftime("%Y-%m-%d")
    parser.add_argument("--start", default=default_start, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", default=default_end, help="End date (YYYY-MM-DD)")
    parser.add_argument("--type", default="trades", help="Data type (trades, book_snapshot_5_100ms, etc.)")
    parser.add_argument("--output", default="data/raw/tardis", help="Output directory")
    
    args = parser.parse_args()
    
    api_key = os.environ.get("TARDIS_API_KEY")
    if not api_key:
        print("Error: TARDIS_API_KEY not found in environment")
        return

    os.makedirs(args.output, exist_ok=True)
    
    print(f"Downloading {args.type} for {args.symbol} from {args.exchange} ({args.start} to {args.end})...")
    
    datasets.download(
        exchange=args.exchange,
        data_types=[args.type],
        from_date=args.start,
        to_date=args.end,
        symbols=[args.symbol],
        api_key=api_key,
        download_dir=args.output,
    )
    print(f"Download complete. Files saved to {args.output}")

if __name__ == "__main__":
    main()
