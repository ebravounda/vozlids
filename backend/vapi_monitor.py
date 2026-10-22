"""Super admin: everything happening in Vapi — calls and why they ended, each number's wiring, errors and spend."""
import json
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


def _transfer(c: dict) -> dict | None:
    for m in c.get("messages") or []:
        for t in m.get("toolCalls") or []:
            if (t.get("function") or {}).get("name") == "transferCall":
                try:
                    to = json.loads(t["function"].get("arguments") or "{}").get("destination", "")
                except ValueError:
                    to = ""
                return {"at": m.get("secondsFromStart") or 0, "to": to}
    return None


def _row(c: dict, phones: dict) -> dict:
    p = phones.get(c.get("phoneNumberId")) or {}
    label, level = reason(c.get("endedReason") or "", (c.get("assistant") or {}).get("firstMessage") or "")
    return {"id": c["id"], "at": c.get("createdAt"), "direction": "entrante" if c.get("type") == "inboundPhoneCall" else
            "web" if c.get("type") == "webCall" else "saliente", "number": p.get("number") or "—", "owner": p.get("owner") or "Web / demo",
            "tenant_id": p.get("tenant_id") or "", "customer": (c.get("customer") or {}).get("number") or "—", "status": c.get("status"),
            "seconds": _secs(c), "cost": round(c.get("cost") or 0, 4), "reason": label, "level": level, "code": c.get("endedReason") or "",
            "transferred": _done(c), **_human(c)}


def _done(c: dict) -> bool:
    ts = (c.get("artifact") or {}).get("transfers")
    if ts:
        return any(t.get("status") not in ("failed", "cancelled") for t in ts)
    return bool(_transfer(c)) and "transfer-failed" not in (c.get("endedReason") or "")


def _human(c: dict) -> dict:
    t, total = _transfer(c), _secs(c)
    if not t or not _done(c) or not total:
        return {"human_seconds": 0, "human_vapi_cost": 0, "transfer_to": (t or {}).get("to", "")}
    secs = max(0, total - round(t["at"]))
    platform = sum(x.get("cost") or 0 for x in c.get("costs") or [] if x.get("type") in ("vapi", "transport"))
    return {"human_seconds": secs, "human_vapi_cost": round(platform * secs / total, 4), "transfer_to": t["to"]}


@router.get("/calls")
async def calls(user=Depends(require_admin)):
    async def load():
        phones = await _phone_map()
        return [_row(c, phones) for c in await monitor.vapi_calls(limit=100)]
    return await _cached("calls", 10, load)


COST_LABEL = {"transcriber": "Transcripción", "model": "IA", "voice": "Voz", "vapi": "Plataforma Vapi", "analysis": "Resumen",
              "transport": "Línea", "knowledge-base": "Base de conocimiento"}


def _ts(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


async def _zadarma_stats(start: datetime, end: datetime) -> list:
    r = await Z.call("GET", "/v1/statistics/", {"start": start.strftime("%Y-%m-%d %H:%M:%S"), "end": end.strftime("%Y-%m-%d %H:%M:%S")})
    return r.get("stats") or []


def _match(stats: list, c: dict, to: str) -> list:
    lo, hi = _ts(c["startedAt"]) - timedelta(minutes=1), _ts(c.get("endedAt") or c["startedAt"]) + timedelta(minutes=5)
    out = []
    for s in stats:
        try:
            at = datetime.strptime(s.get("callstart", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if str(s.get("to")) == to.lstrip("+") and lo <= at <= hi:
            out.append(s)
    return out


async def _zadarma_leg(c: dict, to: str) -> dict | None:
    if not to or not (await Z.creds()).get("key"):
        return None
    try:
        stats = await _zadarma_stats(_ts(c["startedAt"]) - timedelta(minutes=1), _ts(c.get("endedAt") or c["startedAt"]) + timedelta(minutes=5))
    except Z.ZadarmaError as e:
        return {"error": str(e)[:200]}
    rows = _match(stats, c, to)
    if not rows:
        return {"seconds": 0, "cost": 0, "currency": "", "note": "Zadarma aún no muestra esta llamada (puede tardar unos minutos)"}
    return {"seconds": sum(int(s.get("billseconds") or 0) for s in rows), "cost": round(sum(float(s.get("billcost") or 0) for s in rows), 4),
            "currency": rows[0].get("currency", ""), "rate": rows[0].get("cost"), "destination": rows[0].get("description", "")}


@router.get("/calls/{call_id}")
async def call_detail(call_id: str, user=Depends(require_admin)):
    c = await vapi.get_call(call_id)
    row, total, t = _row(c, await _phone_map()), _secs(c), _transfer(c)
    sums: dict = {}
    for x in c.get("costs") or []:
        k = COST_LABEL.get(x.get("type"), x.get("type"))
        sums[k] = sums.get(k, 0) + (x.get("cost") or 0)
    items = [{"label": k, "cost": round(v, 4)} for k, v in sums.items() if v]
    human_secs, human_vapi = row["human_seconds"], row["human_vapi_cost"]
    human = None
    if t:
        human = {"to": t["to"], "ok": row["transferred"], "seconds": human_secs, "vapi_cost": human_vapi,
                 "zadarma": await _zadarma_leg(c, t["to"]) if row["transferred"] else None}
    return {**row, "ai": {"seconds": total - human_secs, "cost": round((c.get("cost") or 0) - human_vapi, 4), "items": items},
            "human": human}


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
        days, owners, tr = {}, {}, {}
        raw = await monitor.vapi_calls(since, 1000)
        stats = None
        if any(_human(c)["human_seconds"] for c in raw) and (await Z.creds()).get("key"):
            try:
                stats = await _zadarma_stats(since, datetime.now(timezone.utc))
            except Z.ZadarmaError:
                stats = None
        for c in raw:
            r = _row(c, phones)
            if r["human_seconds"]:
                z = _match(stats, c, r["transfer_to"]) if stats is not None else []
                for key in ("Total", r["owner"]):
                    b = tr.setdefault(key, {"calls": 0, "seconds": 0, "vapi": 0, "zadarma": 0, "zadarma_seconds": 0, "currency": ""})
                    b["calls"] += 1
                    b["seconds"] += r["human_seconds"]
                    b["vapi"] += r["human_vapi_cost"]
                    b["zadarma"] += sum(float(x.get("billcost") or 0) for x in z)
                    b["zadarma_seconds"] += sum(int(x.get("billseconds") or 0) for x in z)
                    b["currency"] = b["currency"] or (z[0].get("currency", "") if z else "")
            for bucket, key in ((days, (r["at"] or "")[:10]), (owners, r["owner"])):
                b = bucket.setdefault(key, {"calls": 0, "minutes": 0, "cost": 0})
                b["calls"] += 1
                b["minutes"] += r["seconds"] / 60
                b["cost"] += r["cost"]
        fmt = lambda d: {k: {"calls": v["calls"], "minutes": round(v["minutes"], 1), "cost": round(v["cost"], 2)} for k, v in d.items()}  # noqa: E731
        transfers = [{"owner": k, "calls": v["calls"], "minutes": round(v["seconds"] / 60, 1), "vapi": round(v["vapi"], 4),
                      "zadarma": round(v["zadarma"], 4) if stats is not None else None, "currency": v["currency"],
                      "vapi_per_min": round(v["vapi"] / (v["seconds"] / 60), 4) if v["seconds"] else 0,
                      "zadarma_per_min": round(v["zadarma"] / (v["zadarma_seconds"] / 60), 4) if v["zadarma_seconds"] else None}
                     for k, v in tr.items()]
        return {"transfers": sorted(transfers, key=lambda x: (x["owner"] != "Total", -x["minutes"])), "days": sorted(({"day": k, **v} for k, v in fmt(days).items()), key=lambda x: x["day"]),
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
    if not fixable and not a["duplicates"] and a["shared"] and (a["transfer_ready"] or not a["numbers"]):
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
