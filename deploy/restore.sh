#!/bin/bash
set -euo pipefail

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <backup_file.sql.gz>"
    echo "Example: $0 backups/backup_20260309_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: File not found: $BACKUP_FILE"
    exit 1
fi

echo "WARNING: This will overwrite the current database with: $BACKUP_FILE"
read -p "Are you sure? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

cd /opt/assetmeetinghelper

echo "=== Restoring database ==="
gunzip -c "$BACKUP_FILE" | docker compose -f docker-compose.prod.yml exec -T db psql -U "${DB_USER:-goac}" "${DB_NAME:-goac}"

echo "=== Restore complete ==="
