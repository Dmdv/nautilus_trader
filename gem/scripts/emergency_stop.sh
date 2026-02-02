#!/bin/bash
set -e

echo "!!! EMERGENCY STOP !!!"
echo "This will STOP all trading containers immediately."

read -p "Type 'STOP' to confirm: " CONFIRM
if [ "$CONFIRM" != "STOP" ]; then
    echo "Aborted"
    exit 1
fi

docker-compose -f docker/production.yml down

echo "Emergency stop complete. Verify exchange positions manually."
