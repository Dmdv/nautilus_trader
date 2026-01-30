import argparse
import sys
import time
import signal

def signal_handler(sig, frame):
    print("\nGracefully shutting down node...")
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    
    parser = argparse.ArgumentParser(description="Run trading node")
    parser.add_argument("--config", required=True, help="Path to config file")
    parser.add_argument("--mode", choices=["dry-run", "shadow", "paper", "production"], required=True)
    args = parser.parse_args()
    
    print(f"Starting Trading Node in {args.mode.upper()} mode...")
    print(f"Config: {args.config}")
    
    if args.mode == "production":
        print("WARNING: PRODUCTION MODE ENABLED")
        
    print("Node running. Press Ctrl+C to stop.")
    
    try:
        # Simulate running loop
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping node...")

if __name__ == "__main__":
    main()

