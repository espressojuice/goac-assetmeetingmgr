#!/bin/bash
set -euo pipefail

cd /opt/assetmeetinghelper

echo "=== Pulling latest code ==="
git pull origin main

echo "=== Running migrations ==="
docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head || true

echo "=== Building containers ==="
docker compose -f docker-compose.prod.yml build

echo "=== Starting services ==="
docker compose -f docker-compose.prod.yml up -d

echo "=== Waiting for startup ==="
sleep 10

echo "=== Health check ==="
docker compose -f docker-compose.prod.yml exec -T api curl -f http://localhost:8000/health

echo ""
echo "=== Deploy complete ==="
docker compose -f docker-compose.prod.yml ps
