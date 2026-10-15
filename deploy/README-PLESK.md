# VozLeads en Plesk (aislado con Docker)

VozLeads corre en **4 contenedores propios** (`vozleads-mongo`, `vozleads-backend`, `vozleads-frontend`, `vozleads-cron`), con su **propia base de datos** (volumen `vozleads_mongo_data`) y su **propia red** (`vozleads_vozleads_net`).
No publica ningún puerto a internet: solo escucha en `127.0.0.1:8710` (API) y `127.0.0.1:8711` (web). No toca Plesk, ni MySQL/MariaDB, ni otros dominios, ni otros contenedores.

## 1. Requisitos (una vez)
- Docker con el plugin `docker compose` (`docker compose version` debe responder).
- `git` y `openssl` (vienen en casi todos los servidores).
- Puertos 8710 y 8711 libres: `ss -ltn | grep -E ':871[01]'` no debe mostrar nada. Si están ocupados, cambia `API_PORT`/`WEB_PORT` en `deploy/.env` y en las reglas nginx del paso 4.

## 2. Descargar el código (por SSH, como root o un usuario con acceso a Docker)
```bash
mkdir -p /opt/vozleads && cd /opt/vozleads
git clone https://github.com/ebravounda/vozlids.git app
cd app/deploy
chmod +x *.sh
```

## 3. Instalar
```bash
./install.sh          # 1ª vez: crea deploy/.env y pide la contraseña de configuración
nano .env             # cambia ADMIN_EMAIL, ADMIN_PASSWORD (nueva y segura) y EMAIL_REPLY_TO
./install.sh          # construye, importa tu configuración (pide la contraseña otra vez) y arranca
```
No uses espacios ni comillas en los valores de `.env`.

## 4. Conectar el dominio en Plesk
1. Plesk → **Sitios web y dominios → vozleads.com → Hosting y DNS → Configuración de Apache y nginx**.
2. En **Directivas adicionales de nginx** pega el contenido de `deploy/plesk-nginx.conf` y pulsa **Aceptar**.
3. SSL: **vozleads.com → Certificados SSL/TLS → Let's Encrypt** (incluye www). En Cloudflare usa modo **Full (strict)**.
4. Cloudflare → Seguridad → WAF: crea una regla **Skip** (omitir Bot Fight / desafíos) para la ruta `/api/` para que Vapi y Stripe puedan enviar sus avisos.

Abre https://vozleads.com y entra con tu ADMIN_EMAIL y ADMIN_PASSWORD.

## 5. Después del primer arranque
- **Super admin → Cobros con Stripe**: pega tu clave secreta *live* (se crea sola la URL de avisos a vozleads.com).
- **Super admin → ElevenLabs** y **Zadarma**: las claves ya vienen importadas; comprueba que salen «Conectado».
- Haz una llamada de prueba con «Llamarme ahora».

## Actualizar (cada vez que haya cambios en GitHub)
```bash
cd /opt/vozleads/app/deploy && ./update.sh
```
Hace copia de seguridad de la base de datos, baja el código, reconstruye y reinicia solo VozLeads (unos segundos de corte).

## Comandos útiles
```bash
docker compose ps                     # estado
docker compose logs -f backend        # registros del servidor
./backup.sh                           # copia manual (deploy/backups, guarda las 14 últimas)
docker compose exec -T mongo mongorestore --drop --archive --gzip < backups/ARCHIVO.archive.gz   # restaurar
docker compose down                   # parar VozLeads (los datos se conservan)
```
Copia automática diaria (opcional): `crontab -e` y añade
`30 3 * * * cd /opt/vozleads/app/deploy && ./backup.sh >/dev/null 2>&1`
