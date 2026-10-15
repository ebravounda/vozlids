#!/usr/bin/env bash
# Vuelve a la versión de VozLeads anterior a la última actualización (solo el programa; los datos no se tocan)
set -euo pipefail
cd "$(dirname "$0")"
DC="docker compose"

for svc in backend frontend; do
  docker image inspect "vozleads-$svc:previous" >/dev/null 2>&1 || { echo "ERROR: no hay versión anterior guardada (se guarda al ejecutar update.sh)."; exit 1; }
done
PREV=$(cat .previous_version 2>/dev/null || true)
CUR=$(git -C .. rev-parse --short HEAD)
echo ">> Versión actual: $CUR · se volverá a: ${PREV:0:7}"
if [ "${1:-}" != "-y" ]; then
  read -r -p "¿Volver a la versión anterior? Tus leads, citas y clientes no se tocan. [s/N] " ans
  [[ "$ans" =~ ^[sSyY]$ ]] || { echo "Cancelado."; exit 0; }
fi

for svc in backend frontend; do
  docker tag "vozleads-$svc:latest" "vozleads-$svc:failed" 2>/dev/null || true
  docker tag "vozleads-$svc:previous" "vozleads-$svc:latest"
done
[ -n "$PREV" ] && git -C .. cat-file -e "$PREV" 2>/dev/null && git -C .. reset --hard -q "$PREV"
$DC up -d --no-build --remove-orphans
sleep 8
set -a; . ./.env; set +a
if curl -fsS "http://127.0.0.1:$API_PORT/api/" >/dev/null; then
  echo ">> Listo: VozLeads funciona con la versión anterior (${PREV:0:7})."
  echo ">> Cuando el problema esté corregido, actualiza de nuevo con ./update.sh"
else
  echo "ERROR: el backend no responde tras volver atrás"; $DC logs --tail 50 backend; exit 1
fi
