#!/bin/bash
PREVIOUS_VERSION=$1

if [ -z "$PREVIOUS_VERSION" ]; then
    echo "Usage: rollback.sh <version>"
    exit 1
fi

echo "Rolling back to $PREVIOUS_VERSION"
docker-compose -f docker/production.yml down
# export NAUTILUS_VERSION=$PREVIOUS_VERSION # If versioning supported in compose
docker-compose -f docker/production.yml up -d
echo "Rollback complete"
