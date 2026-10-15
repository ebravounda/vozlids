import io
import json
import re
from datetime import timedelta, timezone
import zipfile
from datetime import datetime
from pathlib import Path
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, field_validator
import services as S
import landing
import vapi
from auth import get_current_user
from extra_routes import require_admin
from countries import COUNTRIES
from db import db
from models import now_iso

router = APIRouter(prefix="/api")
JS = (Path(__file__).parent / "assets" / "widget.js").read_text()
DEFAULTS = {"agent_id": "", "text": "Solicitar llamada", "color": "#2563EB", "position": "right",
            "hours_only": False, "greeting": "", "greeting_delay": 6}


class WidgetIn(BaseModel):
    agent_id: str = Field(min_length=1, max_length=40)
    text: str = Field("Solicitar llamada", min_length=2, max_length=30)
    color: str = "#2563EB"
    position: str = Field("right", pattern="^(left|right)$")
    hours_only: bool = False
    greeting: str = Field("", max_length=120)
    greeting_delay: int = Field(6, ge=1, le=60)

    @field_validator("color")
    @classmethod
    def hex_color(cls, v: str) -> str:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", v):
            raise ValueError("Color no válido")
        return v.upper()


async def tenant_widget(tid: str) -> dict:
    doc = await db.widgets.find_one({"tenant_id": tid})
    if not doc:
        doc = {"tenant_id": tid, **DEFAULTS, "created_at": now_iso()}
        res = await db.widgets.insert_one(doc)
        doc["_id"] = res.inserted_id
    return {**DEFAULTS, **{k: v for k, v in doc.items() if k in DEFAULTS}, "id": str(doc["_id"])}


@router.get("/widget")
async def get_widget(user=Depends(get_current_user)):
    return await tenant_widget(user["id"])


@router.put("/widget")
async def put_widget(body: WidgetIn, user=Depends(get_current_user)):
    import plan_limits as PL
    await PL.require(user["id"], "widget")
    if not ObjectId.is_valid(body.agent_id) or not await db.agents.find_one({"_id": ObjectId(body.agent_id), "tenant_id": user["id"]}):
        raise HTTPException(422, "Elige uno de tus agentes")
    await tenant_widget(user["id"])
    await db.widgets.update_one({"tenant_id": user["id"]}, {"$set": {**body.model_dump(), "updated_at": now_iso()}})
    return await tenant_widget(user["id"])


async def open_now(tid: str, country: str) -> bool:
    av = await S.get_availability(tid)
    now = datetime.now(S.tz_of(country))
    day = av["days"][now.weekday()]
    return bool(day.get("enabled")) and day["start"] <= now.strftime("%H:%M") < day["end"]


@router.get("/public/widget/{wid}")
async def public_widget(wid: str):
    doc = await db.widgets.find_one({"_id": ObjectId(wid)}) if ObjectId.is_valid(wid) else None
    agent = await db.agents.find_one({"_id": ObjectId(doc["agent_id"])}) if doc and ObjectId.is_valid(doc.get("agent_id", "")) else None
    if not agent or not agent.get("active"):
        raise HTTPException(404, "Botón no disponible")
    country = agent.get("country", "ES")
    show = not doc.get("hours_only") or await open_now(doc["tenant_id"], country)
    return JSONResponse({"agent_id": str(agent["_id"]), "show": show, "form_url": f"{vapi.public_url()}/f/{agent['_id']}",
            "business_name": agent.get("business_name", ""), "country": COUNTRIES.get(country, {}).get("name", ""),
            **{k: doc.get(k, DEFAULTS[k]) for k in ("text", "color", "position", "greeting", "greeting_delay")}},
                        headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "public, max-age=60"})


@router.get("/public/widget.js")
async def widget_js():
    return Response(JS.replace("__API__", vapi.public_url()), media_type="application/javascript",
                    headers={"Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*"})


WP = """<?php
/**
 * Plugin Name: VozLeads – Botón Solicitar llamada
 * Description: Añade un botón flotante para que tus clientes pidan una llamada de tu asistente telefónico con IA.
 * Version: 1.0.0
 * Author: VozLeads
 * Author URI: __API__
 * License: GPL2
 */
if (!defined('ABSPATH')) exit;

function vozleads_widget_id() { return get_option('vozleads_widget_id', '__WID__'); }

add_action('wp_enqueue_scripts', function () {
    $id = vozleads_widget_id();
    if (!$id) return;
    wp_enqueue_script('vozleads-widget', '__API__/api/public/widget.js', array(), '1.0.0', true);
});

add_filter('script_loader_tag', function ($tag, $handle) {
    if ($handle !== 'vozleads-widget') return $tag;
    return str_replace(' src=', ' async data-id="' . esc_attr(vozleads_widget_id()) . '" src=', $tag);
}, 10, 2);

add_action('admin_menu', function () {
    add_options_page('VozLeads', 'VozLeads', 'manage_options', 'vozleads', 'vozleads_settings_page');
});

add_action('admin_init', function () {
    register_setting('vozleads', 'vozleads_widget_id', array('sanitize_callback' => 'sanitize_text_field'));
});

function vozleads_settings_page() { ?>
  <div class="wrap">
    <h1>VozLeads · Botón Solicitar llamada</h1>
    <p>El botón ya está activo en tu web. El texto, el color, la posición y el horario se cambian desde tu panel de VozLeads.</p>
    <form method="post" action="options.php">
      <?php settings_fields('vozleads'); ?>
      <table class="form-table"><tr><th scope="row">ID del botón</th>
        <td><input type="text" name="vozleads_widget_id" value="<?php echo esc_attr(vozleads_widget_id()); ?>" class="regular-text" /></td></tr></table>
      <?php submit_button(); ?>
    </form>
  </div>
<?php }
"""


@router.get("/widget/wordpress.zip")
async def wordpress_zip(user=Depends(get_current_user)):
    w = await tenant_widget(user["id"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("vozleads-widget/vozleads-widget.php", WP.replace("__API__", vapi.public_url()).replace("__WID__", w["id"]))
        z.writestr("vozleads-widget/readme.txt", "=== VozLeads – Botón Solicitar llamada ===\nStable tag: 1.0.0\n\n"
                   "Instala el plugin, actívalo y el botón aparece en tu web. Ajustes > VozLeads para cambiar el ID.\n")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="vozleads-widget.zip"'})


ANSWERED = ["calificado", "no_interesado", "cita_agendada", "venta", "no_llamar", "atendida", "en_curso"]
_hits: dict = {}


@router.post("/public/widget/{wid}/event")
async def widget_event(wid: str, request: Request):
    try:
        kind = json.loads((await request.body())[:200] or b"{}").get("t")
    except ValueError:
        kind = None
    if kind not in ("view", "open") or not ObjectId.is_valid(wid):
        return Response(status_code=204)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = (day, landing.client_ip(request), wid, kind)
    if _hits.get(key, 0) >= 30:
        return Response(status_code=204)
    if len(_hits) > 50000:
        _hits.clear()
    _hits[key] = _hits.get(key, 0) + 1
    doc = await db.widgets.find_one({"_id": ObjectId(wid)}, {"tenant_id": 1})
    if doc:
        await db.widget_stats.update_one({"widget_id": wid, "day": day}, {"$inc": {f"{kind}s": 1},
                                         "$setOnInsert": {"tenant_id": doc["tenant_id"]}}, upsert=True)
    return Response(status_code=204, headers={"Access-Control-Allow-Origin": "*"})


async def funnel(tenant_id: str | None, days: int) -> dict:
    days = max(1, min(days, 365))
    start = datetime.now(timezone.utc).date() - timedelta(days=days - 1)
    span = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    daily = {d: {"day": d, "views": 0, "opens": 0, "submitted": 0, "answered": 0, "appointments": 0} for d in span}
    tq = {"tenant_id": tenant_id} if tenant_id else {}
    async for s in db.widget_stats.find({**tq, "day": {"$gte": span[0]}}):
        if s["day"] in daily:
            daily[s["day"]]["views"] += s.get("views", 0)
            daily[s["day"]]["opens"] += s.get("opens", 0)
    ids = []
    async for ld in db.leads.find({**tq, "source": "widget", "created_at": {"$gte": span[0]}}, {"created_at": 1, "status": 1}):
        d = daily.get(ld["created_at"][:10])
        ids.append(str(ld["_id"]))
        if d:
            d["submitted"] += 1
            d["answered"] += ld.get("status") in ANSWERED
    async for a in db.appointments.find({"lead_id": {"$in": ids}}, {"created_at": 1}):
        d = daily.get((a.get("created_at") or "")[:10])
        if d:
            d["appointments"] += 1
    rows = list(daily.values())
    totals = {k: sum(r[k] for r in rows) for k in ("views", "opens", "submitted", "answered", "appointments")}
    return {"totals": totals, "daily": rows, "days": days}


@router.get("/widget/stats")
async def my_stats(days: int = 30, user=Depends(get_current_user)):
    return await funnel(user["id"], days)


@router.get("/admin/monitor/widget-stats")
async def all_stats(days: int = 30, user=Depends(require_admin)):
    return await funnel(None, days)
