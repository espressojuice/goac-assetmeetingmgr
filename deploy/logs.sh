#!/bin/bash

cd /opt/assetmeetinghelper
docker compose -f docker-compose.prod.yml logs -f ${1:-}
