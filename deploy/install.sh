#!/usr/bin/env bash
# Primera instalación de VozLeads (aislado en Docker, no toca otros sistemas)
set -euo pipefail
cd "$(dirname "$0")"
DC="docker compose"

command -v docker >/dev/null || { echo "ERROR: Docker no está instalado."; exit 1; }
$DC version >/dev/null 2>&1 || { echo "ERROR: falta 'docker compose' (plugin v2)."; exit 1; }

if [ ! -f .env ]; then
  cp env.example .env
  for k in JWT_SECRET VAPI_WEBHOOK_SECRET WEBHOOK_CRON_SECRET; do
    sed -i "s|^$k=.*|$k=$(openssl rand -hex 32)|" .env
  done
  chmod 600 .env
  if [ -f data/env-secrets.enc ]; then
    read -rsp "Contraseña de la configuración (te la di en el chat): " PASS; echo
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in data/env-secrets.enc -pass "pass:$PASS" > .env.secrets
    while IFS='=' read -r k v; do
      [ -n "$k" ] && sed -i "s|^$k=.*|$k=$v|" .env
    done < .env.secrets
    rm -f .env.secrets
    echo ">> Claves de Vapi y Emergent cargadas."
  fi
  echo ">> Creado deploy/.env. Rellena los valores CAMBIAR (nano deploy/.env) y vuelve a ejecutar ./install.sh"
  exit 0
fi
grep -q "CAMBIAR" .env && { echo "ERROR: aún hay valores CAMBIAR en deploy/.env"; exit 1; }
set -a; . ./.env; set +a

for p in "$API_PORT" "$WEB_PORT"; do
  if ss -ltn | awk '{print $4}' | grep -qE "[:.]$p$" && ! $DC ps -q | grep -q .; then
    echo "ERROR: el puerto $p ya está en uso por otro servicio. Cambia API_PORT/WEB_PORT en deploy/.env"; exit 1
  fi
done

echo ">> Construyendo VozLeads (tarda unos minutos la primera vez)…"
$DC build
$DC up -d mongo
sleep 5

if [ -f data/vozleads-config.json.enc ] && [ ! -f data/.imported ]; then
  echo ">> Importando tu configuración (agentes, voces, plantillas, planes y ajustes)."
  read -rsp "Contraseña de la configuración: " PASS; echo
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -in data/vozleads-config.json.enc -pass "pass:$PASS" \
    | $DC run --rm -T --no-deps backend python tools/import_config.py
  touch data/.imported
fi

$DC up -d
sleep 8
curl -fsS "http://127.0.0.1:$API_PORT/api/" >/dev/null && echo ">> Backend OK en 127.0.0.1:$API_PORT" || echo "AVISO: el backend aún no responde; revisa: docker compose logs backend"
curl -fsS "http://127.0.0.1:$WEB_PORT/" >/dev/null && echo ">> Web OK en 127.0.0.1:$WEB_PORT"
echo ">> Listo. Ahora añade las reglas de nginx en Plesk (ver deploy/README-PLESK.md, paso 4)."
