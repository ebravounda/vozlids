#!/usr/bin/env bash
# Copia de seguridad de la base de datos de VozLeads (guarda las 14 últimas)
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
set -a; . ./.env; set +a
FILE="backups/vozleads-$(date +%Y%m%d-%H%M%S).archive.gz"
docker compose exec -T mongo mongodump --db "$DB_NAME" --archive --gzip > "$FILE"
echo ">> Copia guardada en deploy/$FILE"
ls -1t backups/*.archive.gz | tail -n +15 | xargs -r rm --
