import argparse
import sys
from nautilus_trader.persistence.catalog import ParquetDataCatalog

def main():
    parser = argparse.ArgumentParser(description="Validate data catalog")
    parser.add_argument("--catalog", default="data/catalog", help="Catalog path")
    args = parser.parse_args()
    
    try:
        catalog = ParquetDataCatalog(args.catalog)
        print(f"Validating catalog at {args.catalog}...")
        
        instruments = catalog.instruments()
        print(f"Found {len(instruments)} instruments.")
        
        for instrument in instruments:
            print(f"  - {instrument.id} ({instrument.asset_class})")
            
        # TODO: Add deeper validation logic (checking for gaps, corrupted files)
        
        print("Validation complete.")
    except Exception as e:
        print(f"Error validating catalog: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
