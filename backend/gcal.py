"""Google Calendar two-way sync per tenant (OAuth app configured by the super admin)."""
import asyncio
import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import httpx
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
import os
import services as S
import vapi
from auth import get_current_user
from db import db
from extra_routes import require_admin
from models import now_iso

log = logging.getLogger("vozlead.gcal")
router = APIRouter(prefix="/api")
SCOPE = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.freebusy https://www.googleapis.com/auth/userinfo.email"
API = "https://www.googleapis.com/calendar/v3"
_busy_cache: dict = {}


def redirect_uri() -> str:
    return f"{vapi.public_url()}/api/oauth/calendar/callback"


async def app_cfg() -> dict:
    return await db.platform_settings.find_one({"_id": "google"}) or {}


async def _tenant(tid: str) -> dict:
    return await db.users.find_one({"_id": ObjectId(tid)}, {"google_calendar": 1, "country": 1}) or {}


async def _token(tid: str) -> str | None:
    u = await _tenant(tid)
    g = u.get("google_calendar") or {}
    if not g.get("refresh_token"):
        return None
    if g.get("access_token") and g.get("expires_at", 0) > time.time() + 60:
        return g["access_token"]
    cfg = await app_cfg()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post("https://oauth2.googleapis.com/token", data={
            "client_id": cfg.get("client_id"), "client_secret": cfg.get("client_secret"),
            "refresh_token": g["refresh_token"], "grant_type": "refresh_token"})
    if r.status_code >= 400:
        await db.users.update_one({"_id": ObjectId(tid)}, {"$set": {"google_calendar.error": "Google rechazó el acceso. Vuelve a conectar."}})
        return None
    d = r.json()
    await db.users.update_one({"_id": ObjectId(tid)}, {"$set": {"google_calendar.access_token": d["access_token"],
                                                                 "google_calendar.expires_at": time.time() + d.get("expires_in", 3600),
                                                                 "google_calendar.error": None}})
    return d["access_token"]


async def _call(tid: str, method: str, path: str, **kw):
    tok = await _token(tid)
    if not tok:
        return None
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.request(method, f"{API}{path}", headers={"Authorization": f"Bearer {tok}"}, **kw)
    if r.status_code >= 400 and r.status_code != 404 and r.status_code != 410:
        log.warning("Google Calendar %s %s -> %s %s", method, path, r.status_code, r.text[:200])
        return None
    return r.json() if r.content else {}


def _tz(country: str) -> str:
    return S.tz_of(country).key


# ---------- Push appointments ----------
async def push(appt_id) -> None:
    a = await db.appointments.find_one({"_id": ObjectId(appt_id) if isinstance(appt_id, str) else appt_id})
    if not a:
        return
    u = await _tenant(a["tenant_id"])
    if not (u.get("google_calendar") or {}).get("refresh_token"):
        return
    slot = (await S.get_availability(a["tenant_id"]))["slot_minutes"]
    start = datetime.fromisoformat(a["start"])
    end = start + timedelta(minutes=a.get("duration_minutes") or slot)
    tz = _tz(u.get("country", "ES"))
    body = {"summary": f"Cita: {a['lead_name']}", "description": "\n".join(filter(None, [
        f"Teléfono: {a['lead_phone']}" if a.get("lead_phone") else "", a.get("notes") or "",
        "Reservada por el agente IA de VozLeads" if a.get("source") != "manual" else "Creada en VozLeads"])),
        "start": {"dateTime": start.isoformat(), "timeZone": tz}, "end": {"dateTime": end.isoformat(), "timeZone": tz},
        "extendedProperties": {"private": {"vozleads_id": str(a["_id"])}}}
    if a.get("google_event_id"):
        res = await _call(a["tenant_id"], "PATCH", f"/calendars/primary/events/{a['google_event_id']}", json=body)
        if res is not None and res.get("id"):
            return
    res = await _call(a["tenant_id"], "POST", "/calendars/primary/events", json=body)
    if res and res.get("id"):
        await db.appointments.update_one({"_id": a["_id"]}, {"$set": {"google_event_id": res["id"]}})


async def remove(tid: str, event_id: str | None) -> None:
    if event_id:
        await _call(tid, "DELETE", f"/calendars/primary/events/{event_id}")


def sync(appt_id) -> None:
    asyncio.create_task(push(appt_id))


def unsync(tid: str, event_id: str | None) -> None:
    if event_id:
        asyncio.create_task(remove(tid, event_id))


# ---------- Busy times from Google ----------
async def busy(tid: str, day_from: str, day_to: str) -> list[tuple[str, str]]:
    """Busy intervals (local 'YYYY-MM-DDTHH:MM') from Google, excluding events created by VozLeads."""
    key = (tid, day_from, day_to)
    hit = _busy_cache.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    u = await _tenant(tid)
    if not (u.get("google_calendar") or {}).get("refresh_token"):
        return []
    tz = S.tz_of(u.get("country", "ES"))
    lo = datetime.fromisoformat(f"{day_from}T00:00").replace(tzinfo=tz)
    hi = datetime.fromisoformat(f"{day_to}T00:00").replace(tzinfo=tz)
    res = await _call(tid, "GET", "/calendars/primary/events", params={
        "timeMin": lo.isoformat(), "timeMax": hi.isoformat(), "singleEvents": "true", "maxResults": 250, "orderBy": "startTime"})
    out = []
    for e in (res or {}).get("items", []):
        if (e.get("extendedProperties") or {}).get("private", {}).get("vozleads_id") or e.get("transparency") == "transparent":
            continue
        s, en = e.get("start", {}), e.get("end", {})
        if s.get("dateTime"):
            a = datetime.fromisoformat(s["dateTime"].replace("Z", "+00:00")).astimezone(tz)
            b = datetime.fromisoformat(en["dateTime"].replace("Z", "+00:00")).astimezone(tz)
        elif s.get("date"):
            a = datetime.fromisoformat(f"{s['date']}T00:00").replace(tzinfo=tz)
            b = datetime.fromisoformat(f"{en['date']}T00:00").replace(tzinfo=tz)
        else:
            continue
        out.append((a.strftime("%Y-%m-%dT%H:%M"), b.strftime("%Y-%m-%dT%H:%M"), e.get("summary", "Ocupado")))
    _busy_cache[key] = (time.time() + 60, out)
    return out


# ---------- Super admin: OAuth app ----------
class GoogleAppIn(BaseModel):
    client_id: str = Field(min_length=10, max_length=200)
    client_secret: str = Field("", max_length=200)


@router.get("/admin/google")
async def admin_google(user=Depends(require_admin)):
    cfg = await app_cfg()
    return {"configured": bool(cfg.get("client_id") and cfg.get("client_secret")), "client_id": cfg.get("client_id", ""),
            "redirect_uri": redirect_uri(), "origin": os.environ["APP_PUBLIC_URL"].rstrip("/"),
            "connected_accounts": await db.users.count_documents({"google_calendar.refresh_token": {"$exists": True}})}


@router.put("/admin/google")
async def admin_google_save(body: GoogleAppIn, user=Depends(require_admin)):
    secret = body.client_secret or (await app_cfg()).get("client_secret", "")
    if not body.client_id.endswith(".apps.googleusercontent.com"):
        raise HTTPException(422, "El ID de cliente termina en .apps.googleusercontent.com")
    if len(secret) < 10:
        raise HTTPException(422, "Falta el secreto de cliente")
    await db.platform_settings.update_one({"_id": "google"}, {"$set": {"client_id": body.client_id.strip(), "client_secret": secret.strip(),
                                                                       "updated_at": now_iso()}}, upsert=True)
    return await admin_google(user)


@router.delete("/admin/google")
async def admin_google_delete(user=Depends(require_admin)):
    await db.platform_settings.delete_one({"_id": "google"})
    return {"ok": True}


# ---------- Tenant: connect ----------
@router.get("/google/status")
async def status(user=Depends(get_current_user)):
    cfg = await app_cfg()
    g = (await _tenant(user["id"])).get("google_calendar") or {}
    return {"available": bool(cfg.get("client_id") and cfg.get("client_secret")), "connected": bool(g.get("refresh_token")),
            "email": g.get("email"), "connected_at": g.get("connected_at"), "error": g.get("error")}


@router.post("/google/connect")
async def connect(user=Depends(get_current_user)):
    import plan_limits as PL
    await PL.require(user["id"], "agenda_pro")
    cfg = await app_cfg()
    if not cfg.get("client_id"):
        raise HTTPException(409, "Google Calendar aún no está disponible. Contacta con soporte.")
    state = secrets.token_urlsafe(24)
    await db.oauth_states.insert_one({"_id": state, "tenant_id": user["id"], "created_at": datetime.now(timezone.utc)})
    q = {"client_id": cfg["client_id"], "redirect_uri": redirect_uri(), "response_type": "code", "scope": SCOPE,
         "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "state": state}
    return {"url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(q)}


@router.get("/oauth/calendar/callback")
async def callback(state: str = "", code: str = "", error: str = ""):
    back = os.environ["APP_PUBLIC_URL"].rstrip("/") + "/app/agenda"
    st = await db.oauth_states.find_one_and_delete({"_id": state}) if state else None
    if not st or error or not code:
        return RedirectResponse(f"{back}?google=error")
    cfg = await app_cfg()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post("https://oauth2.googleapis.com/token", data={
            "code": code, "client_id": cfg.get("client_id"), "client_secret": cfg.get("client_secret"),
            "redirect_uri": redirect_uri(), "grant_type": "authorization_code"})
        if r.status_code >= 400 or not r.json().get("refresh_token"):
            log.warning("Google token exchange failed: %s", r.text[:200])
            return RedirectResponse(f"{back}?google=error")
        tok = r.json()
        info = (await c.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {tok['access_token']}"})).json()
    await db.users.update_one({"_id": ObjectId(st["tenant_id"])}, {"$set": {"google_calendar": {
        "refresh_token": tok["refresh_token"], "access_token": tok["access_token"], "expires_at": time.time() + tok.get("expires_in", 3600),
        "email": info.get("email"), "connected_at": now_iso(), "error": None}}})
    async for a in db.appointments.find({"tenant_id": st["tenant_id"], "start": {"$gte": S.madrid_now().strftime("%Y-%m-%d")}}, {"_id": 1}):
        sync(a["_id"])
    return RedirectResponse(f"{back}?google=ok")


@router.post("/google/disconnect")
async def disconnect(user=Depends(get_current_user)):
    g = (await _tenant(user["id"])).get("google_calendar") or {}
    if g.get("refresh_token"):
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                await c.post("https://oauth2.googleapis.com/revoke", data={"token": g["refresh_token"]})
        except httpx.HTTPError:
            pass
    await db.users.update_one({"_id": ObjectId(user["id"])}, {"$unset": {"google_calendar": ""}})
    await db.appointments.update_many({"tenant_id": user["id"]}, {"$unset": {"google_event_id": ""}})
    return {"ok": True}


@router.get("/google/busy")
async def busy_route(start: str, end: str, user=Depends(get_current_user)):
    return [{"start": a, "end": b, "title": t} for a, b, t in await busy(user["id"], start[:10], end[:10])]


async def ensure_indexes() -> None:
    await db.oauth_states.create_index("created_at", expireAfterSeconds=900)
