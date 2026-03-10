#!/bin/bash
set -euo pipefail

cd /opt/assetmeetinghelper
docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head
