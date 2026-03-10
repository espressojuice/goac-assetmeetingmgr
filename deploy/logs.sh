#!/bin/bash

cd /home/deploy/goac-assetmeetingmgr
docker compose -f docker-compose.prod.yml logs -f ${1:-}
