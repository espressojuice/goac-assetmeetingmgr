#!/bin/bash
set -euo pipefail

cd /opt/assetmeetinghelper

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="backups/backup_${TIMESTAMP}.sql.gz"

echo "=== Creating backup ==="
docker compose -f docker-compose.prod.yml exec -T db pg_dump -U "${DB_USER:-goac}" "${DB_NAME:-goac}" | gzip > "$BACKUP_FILE"

echo "Backup saved: $BACKUP_FILE"
ls -lh "$BACKUP_FILE"
