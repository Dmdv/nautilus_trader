#!/bin/bash
set -e

BACKUP_DIR="backups/nautilus/$(date +%Y%m%d)"
mkdir -p "$BACKUP_DIR/logs"

echo "Backing up configuration..."
cp -r config/ "$BACKUP_DIR/config/" 2>/dev/null || true

echo "Backing up logs..."
find logs/ -mtime -7 -name "*.log" -exec cp {} "$BACKUP_DIR/logs/" \; 2>/dev/null || true

echo "Backup complete: $BACKUP_DIR"
