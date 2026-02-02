#!/bin/bash
set -e

STRATEGY=$1
VENUE=$2
VERSION=$(git describe --tags --always 2>/dev/null || echo "latest")

echo "=== Production Deployment ==="
echo "Strategy: $STRATEGY"
echo "Venue: $VENUE"
echo "Version: $VERSION"

# Confirm deployment
read -p "Proceed with production deployment? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled"
    exit 1
fi

# Deploy
echo "Deploying..."
docker-compose -f docker/production.yml up -d

# Verify
echo "Verifying deployment..."
sleep 10
docker ps | grep nautilus

echo "=== Deployment Complete ==="
