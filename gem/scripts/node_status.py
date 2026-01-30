import argparse
import os

def main():
    parser = argparse.ArgumentParser(description="Check node status")
    parser.add_argument("--mode", choices=["dry-run", "shadow", "paper", "production"], default="production")
    args = parser.parse_args()
    
    # In a real implementation, this would check a PID file or query a control socket/API
    print(f"Checking status for {args.mode} node...")
    
    # Placeholder logic
    pid_file = f"/tmp/nautilus_{args.mode}.pid"
    if os.path.exists(pid_file):
        print(f"Node is RUNNING (PID: {open(pid_file).read().strip()})")
    else:
        print("Node is STOPPED")

if __name__ == "__main__":
    main()
