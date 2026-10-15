#!/usr/bin/env bash
# Actualiza VozLeads desde GitHub sin cortar el servicio más de unos segundos
set -euo pipefail
cd "$(dirname "$0")"
DC="docker compose"

./backup.sh
git -C .. pull --ff-only
grep -q "^STRIPE_API_KEY=." .env || { sed -i '/^STRIPE_API_KEY=/d' .env; printf "\nSTRIPE_API_KEY=sk_test_emergent\n" >> .env; echo ">> Activada la cuenta de pruebas de Stripe"; }
$DC build
$DC up -d --remove-orphans
sleep 8
set -a; . ./.env; set +a
curl -fsS "http://127.0.0.1:$API_PORT/api/" >/dev/null && echo ">> Actualizado y funcionando" || { echo "ERROR: el backend no responde"; $DC logs --tail 50 backend; exit 1; }
docker image prune -f --filter "label=com.docker.compose.project=vozleads" >/dev/null || true
