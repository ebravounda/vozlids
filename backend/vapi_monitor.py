"""Super admin: everything happening in Vapi — calls and why they ended, each number's wiring, errors and spend."""
import logging
import os
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

import emailer
import monitor
import vapi
import zadarma as Z
from db import db
from extra_routes import require_admin

router = APIRouter(prefix="/api/admin/vapi")
log = logging.getLogger(__name__)
_cache: dict = {}

REASONS = {
    "customer-ended-call": ("El cliente colgó", "ok"), "assistant-ended-call": ("El agente terminó la llamada", "ok"),
    "assistant-said-end-call-phrase": ("El agente se despidió", "ok"), "assistant-forwarded-call": ("Pasada a una persona", "ok"),
    "voicemail": ("Buzón de voz", "aviso"), "customer-did-not-answer": ("No contestó", "aviso"), "customer-busy": ("Ocupado", "aviso"),
    "silence-timed-out": ("Cortada por silencio", "aviso"), "exceeded-max-duration": ("Superó la duración máxima", "aviso"),
    "manually-canceled": ("Colgada desde el panel", "ok"),
    "assistant-request-failed": ("Tu servidor no respondió al entrar la llamada", "error"),
    "call.in-progress.sip-completed-call": ("Llamada terminada", "ok"),
    "call.in-progress.error-transfer-failed": ("No se pudo pasar la llamada a la persona", "error"),
    "call.forwarding.operator-busy": ("La persona a la que se pasaba estaba ocupada", "aviso"),
    "call.forwarding.no-answer": ("La persona a la que se pasaba no contestó", "aviso"),
    "assistant-request-returned-error": ("Tu servidor devolvió un error al entrar la llamada", "error"),
}


def reason(code: str, first: str) -> tuple:
    if first.startswith("Hola, gracias por llamar. Ahora mismo no podemos"):
        return "Respondió «no disponible»: número o agente sin asignar, o cuenta sin minutos", "error"
    if not code:
        return "En curso", "ok"
    if code in REASONS:
        return REASONS[code]
    if "sip" in code or "providerfault" in code:
        return f"Fallo de la línea telefónica ({code})", "error"
    if "pipeline" in code or "voice" in code or "llm" in code or "error" in code:
        return f"Fallo de voz o IA ({code})", "error"
    return code, "aviso"


async def _cached(key: str, ttl: int, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = await fn()
    _cache[key] = (time.time(), val)
    return val


async def _phone_map() -> dict:
    owners = {str(u["_id"]): u.get("business_name") or u["email"] async for u in db.users.find({}, {"business_name": 1, "email": 1})}
    out = {}
    async for r in db.tenant_numbers.find({"status": {"$ne": "liberado"}}):
        info = {"number": r.get("number"), "tenant_id": r.get("tenant_id"), "owner": owners.get(r.get("tenant_id"), "Plataforma")}
        for k in ("phone_number_id", "inbound_phone_number_id"):
            if r.get(k):
                out[r[k]] = info
    for n in vapi.STATE["numbers"].values():
        out.setdefault(n.get("phone_number_id"), {"number": n.get("number"), "tenant_id": "", "owner": "Plataforma"})
    for p in await _cached("phones", 120, lambda: vapi._list("/phone-number")):
        digits = str(p.get("number") or "").removeprefix("00")
        out.setdefault(p["id"], {"number": f"+{digits}" if digits else p.get("sipUri"), "tenant_id": "", "owner": "Sin asignar en VozLeads"})
    return out


def _secs(c: dict) -> int:
    try:
        a, b = (datetime.fromisoformat(c[k].replace("Z", "+00:00")) for k in ("startedAt", "endedAt"))
        return max(0, round((b - a).total_seconds()))
    except (KeyError, AttributeError, ValueError):
        return 0


def _row(c: dict, phones: dict) -> dict:
    p = phones.get(c.get("phoneNumberId")) or {}
    label, level = reason(c.get("endedReason") or "", (c.get("assistant") or {}).get("firstMessage") or "")
    return {"id": c["id"], "at": c.get("createdAt"), "direction": "entrante" if c.get("type") == "inboundPhoneCall" else
            "web" if c.get("type") == "webCall" else "saliente", "number": p.get("number") or "—", "owner": p.get("owner") or "Web / demo",
            "tenant_id": p.get("tenant_id") or "", "customer": (c.get("customer") or {}).get("number") or "—", "status": c.get("status"),
            "seconds": _secs(c), "cost": round(c.get("cost") or 0, 4), "reason": label, "level": level, "code": c.get("endedReason") or ""}


@router.get("/calls")
async def calls(user=Depends(require_admin)):
    async def load():
        phones = await _phone_map()
        return [_row(c, phones) for c in await monitor.vapi_calls(limit=100)]
    return await _cached("calls", 10, load)


@router.get("/errors")
async def errors(user=Depends(require_admin)):
    rows = [r for r in await calls(user) if r["level"] == "error"]
    events = await db.vapi_events.find({}, {"_id": 0}).sort("at", -1).to_list(50)
    return {"calls": rows, "events": events}


@router.get("/spend")
async def spend(user=Depends(require_admin)):
    async def load():
        phones = await _phone_map()
        since = datetime.now(timezone.utc) - timedelta(days=13)
        days, owners = {}, {}
        for c in await monitor.vapi_calls(since, 1000):
            r = _row(c, phones)
            for bucket, key in ((days, (r["at"] or "")[:10]), (owners, r["owner"])):
                b = bucket.setdefault(key, {"calls": 0, "minutes": 0, "cost": 0})
                b["calls"] += 1
                b["minutes"] += r["seconds"] / 60
                b["cost"] += r["cost"]
        fmt = lambda d: {k: {"calls": v["calls"], "minutes": round(v["minutes"], 1), "cost": round(v["cost"], 2)} for k, v in d.items()}  # noqa: E731
        return {"days": sorted(({"day": k, **v} for k, v in fmt(days).items()), key=lambda x: x["day"]),
                "owners": sorted(({"owner": k, **v} for k, v in fmt(owners).items()), key=lambda x: -x["cost"])}
    return await _cached("spend", 60, load)


async def audit() -> dict:
    creds = await vapi._list("/credential")
    shared = next((c["id"] for c in creds if c.get("provider") == "byo-sip-trunk" and c.get("name") == vapi.INBOUND_NAME), None)
    dups = [c["id"] for c in creds if c.get("provider") == "byo-sip-trunk" and c["id"] != shared
            and any(g.get("inboundEnabled", True) for g in c.get("gateways") or [])]
    phones = {p["id"]: p for p in await vapi._list("/phone-number")}
    routes = None
    if (await Z.creds()).get("key"):
        routes = {str(n.get("number")): n.get("sip") for n in await Z.my_numbers()}
    owners = {str(u["_id"]): u.get("business_name") or u["email"] async for u in db.users.find({}, {"business_name": 1, "email": 1})}
    rows = []
    async for r in db.tenant_numbers.find({"status": "activo", "number": {"$nin": [None, ""]}}):
        digits, issues = r["number"].lstrip("+"), []
        p = phones.get(r.get("inbound_phone_number_id") or "")
        if not p:
            issues.append("No tiene entrada en Vapi: las llamadas no entran")
        else:
            if p.get("credentialId") != shared:
                issues.append("Su entrada no está en la conexión común")
            if p.get("number") != vapi.inbound_alias(digits):
                issues.append("Usa el identificador antiguo (da «number not found»)")
            url = (p.get("server") or {}).get("url")
            if url != vapi.webhook_url():
                issues.append(f"Avisa a otro servidor: {url or 'ninguno'}")
        if not phones.get(r.get("phone_number_id") or ""):
            issues.append("Falta su conexión de salida: pulsa «Reconfigurar» en Líneas")
        if routes is not None and routes.get(digits) != r.get("inbound_uri"):
            issues.append(f"Zadarma desvía a {routes.get(digits) or 'ningún sitio'}")
        rows.append({"number": r["number"], "owner": owners.get(r.get("tenant_id"), "Plataforma"), "extra": bool(r.get("extra")),
                     "alias": (p or {}).get("number"), "webhook": ((p or {}).get("server") or {}).get("url"), "issues": issues,
                     "ok": not issues, "health": r.get("health"), "health_reason": r.get("health_reason", "")})
    sc = next((c for c in creds if c["id"] == shared), {})
    return {"shared": bool(shared), "transfer_ready": bool((sc.get("outboundAuthenticationPlan") or {}).get("authUsername")), "duplicates": len(dups), "zadarma": routes is not None, "numbers": rows,
            "webhook": vapi.webhook_url()}


@router.get("/numbers")
async def numbers(user=Depends(require_admin)):
    return await _cached("numbers", 20, audit)


async def auto_repair() -> list:
    """Run with line health: fix numbers whose inbound wiring drifted and email the admin what changed."""
    if not (await Z.creds()).get("key") or not os.environ.get("VAPI_API_KEY"):
        return []
    a = await audit()
    fixable = [n for n in a["numbers"] if any("Reconfigurar" not in i for i in n["issues"])]
    if not fixable and not a["duplicates"] and a["shared"]:
        return []
    import lines
    res = await lines.repair(None)
    after = {n["number"]: n["issues"] for n in (await audit())["numbers"]}
    admin = await db.users.find_one({"role": "admin"}, {"email": 1})
    if admin:
        rows = [(n["number"], "Reparado" if not after.get(n["number"]) else "Sigue con fallo: " + "; ".join(after[n["number"]]))
                for n in fixable] or [("Conexiones", "Se quitaron conexiones de entrada duplicadas en Vapi")]
        await emailer.send(admin["email"], "Monitor de Vapi: he reparado llamadas entrantes", "Reparación automática en Vapi", rows,
                           os.environ["APP_PUBLIC_URL"].rstrip("/") + "/app/vapi", cta_label="Abrir Monitor de Vapi")
    await event("auto_repair", "", f"Reparación automática: {len(fixable)} número(s)")
    return res["numbers"]


async def event(kind: str, number: str, detail: str) -> None:
    await db.vapi_events.insert_one({"kind": kind, "number": number, "detail": detail[:300],
                                     "at": datetime.now(timezone.utc).isoformat(), "at_dt": datetime.now(timezone.utc)})


async def ensure_indexes() -> None:
    await db.vapi_events.create_index("at_dt", expireAfterSeconds=14 * 86400)
