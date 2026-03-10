#!/bin/bash
set -euo pipefail

cd /home/deploy/goac-assetmeetingmgr
docker compose -f docker-compose.prod.yml exec -T api alembic upgrade head
