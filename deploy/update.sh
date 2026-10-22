#!/usr/bin/env bash
# Actualiza VozLeads desde GitHub sin cortar el servicio más de unos segundos
set -euo pipefail
cd "$(dirname "$0")"
DC="docker compose"

ensure_swap() {
  local mem swap
  mem=$(awk '/MemAvailable/ {print int($2/1024)}' /proc/meminfo)
  swap=$(awk '/SwapTotal/ {print int($2/1024)}' /proc/meminfo)
  echo ">> Memoria libre: ${mem} MB · swap: ${swap} MB"
  if [ "$swap" -lt 2048 ] && [ ! -f /swapfile-vozleads ]; then
    echo ">> Creando 4 GB de swap para que la compilación no se quede sin memoria (solo la primera vez)"
    fallocate -l 4G /swapfile-vozleads 2>/dev/null || dd if=/dev/zero of=/swapfile-vozleads bs=1M count=4096 status=none
    chmod 600 /swapfile-vozleads && mkswap /swapfile-vozleads >/dev/null && swapon /swapfile-vozleads
    grep -q swapfile-vozleads /etc/fstab || echo "/swapfile-vozleads none swap sw 0 0" >> /etc/fstab
  fi
}

save_previous() {
  local ok=0
  for svc in backend frontend; do
    docker image inspect "vozleads-$svc:latest" >/dev/null 2>&1 && docker tag "vozleads-$svc:latest" "vozleads-$svc:previous" && ok=$((ok+1))
  done
  [ "$ok" = 2 ] && git -C .. rev-parse HEAD > .previous_version && echo ">> Versión actual guardada: si algo falla, vuelve atrás con ./rollback.sh"
}

./backup.sh
ensure_swap
save_previous
OLD=$(git -C .. rev-parse HEAD)
git -C .. pull --ff-only
NEW=$(git -C .. rev-parse HEAD)
grep -q "^STRIPE_API_KEY=." .env || { sed -i '/^STRIPE_API_KEY=/d' .env; printf "\nSTRIPE_API_KEY=sk_test_emergent\n" >> .env; echo ">> Activada la cuenta de pruebas de Stripe"; }
export BUILDKIT_PROGRESS=plain
echo ">> Compilando el backend…"
$DC build backend
if [ "$OLD" = "$NEW" ] || [ -n "$(git -C .. diff --name-only "$OLD" "$NEW" -- frontend)" ] || [ "${FORCE_FRONTEND:-}" = "1" ]; then
  echo ">> Compilando la web (2-6 minutos según el servidor; verás el progreso)…"
  timeout 1500 $DC build frontend || { echo "ERROR: la compilación de la web tardó demasiado o falló. Ejecuta 'free -h' y envíame el resultado."; exit 1; }
else
  echo ">> La web no ha cambiado: se reutiliza la versión actual"
fi
$DC up -d --remove-orphans
set -a; . ./.env; set +a
for i in $(seq 1 20); do curl -fsS "http://127.0.0.1:$API_PORT/api/" >/dev/null 2>&1 && break; sleep 3; done
curl -fsS "http://127.0.0.1:$API_PORT/api/" >/dev/null && echo ">> Actualizado y funcionando" || { echo "ERROR: el backend no responde"; $DC logs --tail 50 backend; echo ">> Para volver a la versión anterior ejecuta: $(pwd)/rollback.sh"; exit 1; }
docker image prune -f --filter "label=com.docker.compose.project=vozleads" >/dev/null || true
