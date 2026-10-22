import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import costs_real as CR
import monitor
import vapi
import zadarma as Z
from db import db
from extra_routes import _parts, get_pricing, require_admin

log = logging.getLogger("vozlead.costs")
router = APIRouter(prefix="/api")
WEEKLY_MIN_USD = 0.01


def _when(r: dict):
    try:
        return datetime.strptime(str(r["callstart"])[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CR.MADRID)
    except (KeyError, ValueError, TypeError):
        return None


async def compare(days: int) -> dict:
    pricing = await get_pricing()
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 29)))
    try:
        stats = await CR._stats(since)
    except Z.ZadarmaError as e:
        return {"rows": [], "totals": {}, "error": str(e)}
    if await CR.learn_rates(stats, pricing):
        pricing = await get_pricing()
    leads = await db.leads.find({"vapi_call_id": {"$ne": None}, "created_at": {"$gte": since.isoformat()}},
                                {"messages": 0, "transcript": 0}).to_list(5000)
    agent_country = {str(a["_id"]): a.get("country", "ES") async for a in db.agents.find({}, {"country": 1})}
    users = {str(u["_id"]): u.get("business_name") or u.get("email") async for u in db.users.find({}, {"business_name": 1, "email": 1})}
    by_num: dict = {}
    for ld in leads:
        by_num.setdefault(CR._digits(ld.get("phone") or "")[-9:], []).append(ld)
    used, rows = set(), []
    t = {"zadarma": 0.0, "panel": 0.0, "zadarma_seconds": 0, "panel_seconds": 0, "ok": 0, "diff": 0, "missing": 0, "free": 0}
    for r in stats:
        when = _when(r)
        cost = CR.to_usd(CR._num(r.get("billcost")), r.get("currency"), pricing)
        secs = int(CR._num(r.get("billseconds")))
        best = None
        for n in {CR._digits(str(r.get("to") or ""))[-9:], CR._digits(str(r.get("from") or ""))[-9:]} - {""}:
            for ld in by_num.get(n, []):
                start = CR._parse(ld.get("started_at") or ld.get("created_at"))
                if when is None or start is None or ld["_id"] in used:
                    continue
                gap = abs((when - (start if start.tzinfo else start.replace(tzinfo=timezone.utc))).total_seconds())
                if gap <= 600 and (best is None or gap < best[0]):
                    best = (gap, ld)
        ld = best[1] if best else None
        if ld is None and cost == 0:
            t["free"] += 1
            continue
        rate = CR.line_rate(ld.get("phone") if ld else "+" + CR._digits(str(r.get("to") or "")),
                            agent_country.get(ld["agent_id"], "ES") if ld else "ES", pricing)
        p = _parts(ld, rate, pricing) if ld else None
        panel = p["linea"] if p else None
        z_rate = round(cost / secs * 60, 4) if secs else None
        status = "missing" if ld is None else ("ok" if abs(panel - cost) < 0.001 else "diff")
        if ld:
            used.add(ld["_id"])
            t["panel"] += panel
            t["panel_seconds"] += ld.get("duration_seconds") or 0
        t["zadarma"] += cost
        t["zadarma_seconds"] += secs
        t[status] += 1
        rows.append({"id": str(r.get("id")), "start": r.get("callstart"), "to": r.get("to"), "destination": r.get("description"),
                     "disposition": r.get("disposition"), "zadarma_seconds": secs, "zadarma_cost": round(cost, 5),
                     "zadarma_rate": z_rate, "panel_rate": rate, "rate_mismatch": z_rate is not None and abs(z_rate - rate) > 0.0015,
                     "panel_seconds": round(ld.get("duration_seconds") or 0) if ld else None,
                     "panel_cost": round(panel, 5) if ld else None, "line_real": bool(p and p["line_real"]),
                     "business": users.get(ld["tenant_id"]) if ld else None,
                     "diff": round((panel or 0) - cost, 5), "status": status})
    t["zadarma"], t["panel"] = round(t["zadarma"], 4), round(t["panel"], 4)
    t["difference"] = round(t["panel"] - t["zadarma"], 4)
    return {"rows": sorted(rows, key=lambda x: x["start"] or "", reverse=True), "totals": t, "error": ""}


@router.get("/admin/costs/zadarma-compare")
async def zadarma_compare(days: int = 30, user=Depends(require_admin)):
    return await compare(days)


# ---------- Per-destination tariffs (learned from Zadarma) ----------
class DestRateIn(BaseModel):
    usd_min: float = Field(ge=0, le=5)


@router.get("/admin/pricing/dest-rates")
async def list_dest_rates(user=Depends(require_admin)):
    doc = await db.platform_settings.find_one({"_id": "dest_rates"}) or {}
    rates = doc.get("rates") or {}
    return {"rates": sorted(({"code": k, **v} for k, v in rates.items()), key=lambda x: x["code"])}


@router.put("/admin/pricing/dest-rates/{code}")
async def set_dest_rate(code: str, body: DestRateIn, user=Depends(require_admin)):
    code = code.upper()
    doc = await db.platform_settings.find_one({"_id": "dest_rates"}) or {}
    if code not in (doc.get("rates") or {}):
        raise HTTPException(404, "País no encontrado")
    await db.platform_settings.update_one({"_id": "dest_rates"}, {"$set": {f"rates.{code}.usd_min": round(body.usd_min, 4),
                                                                           f"rates.{code}.manual": True}})
    return await list_dest_rates(user)


@router.delete("/admin/pricing/dest-rates/{code}/manual")
async def reset_dest_rate(code: str, user=Depends(require_admin)):
    code = code.upper()
    doc = await db.platform_settings.find_one({"_id": "dest_rates"}) or {}
    if code not in (doc.get("rates") or {}):
        raise HTTPException(404, "País no encontrado")
    await db.platform_settings.update_one({"_id": "dest_rates"}, {"$set": {f"rates.{code}.manual": False}})
    return await list_dest_rates(user)


# ---------- Weekly email if Zadarma charges more than the panel counts ----------
async def weekly_check(force: bool = False) -> dict | None:
    now = datetime.now(CR.MADRID)
    week = now.strftime("%G-W%V")
    st = await db.platform_settings.find_one({"_id": "zadarma_weekly"}) or {}
    if not force and (now.weekday() != 0 or now.hour < 9 or st.get("week") == week):
        return None
    await db.platform_settings.update_one({"_id": "zadarma_weekly"}, {"$set": {"week": week, "at": now.isoformat()}}, upsert=True)
    d = await compare(7)
    t = d["totals"]
    if d["error"] or -t["difference"] < WEEKLY_MIN_USD:
        return {"sent": False, "error": d["error"], "totals": t}
    sent = await monitor.notify("zadarma_diff", f"Zadarma te cobró {-t['difference']:.2f} $ más de lo que cuenta el panel", [
        ("Últimos 7 días · Zadarma", f"{t['zadarma']:.4f} $"), ("Últimos 7 días · panel", f"{t['panel']:.4f} $"),
        ("Diferencia", f"{-t['difference']:.4f} $"),
        ("Llamadas", f"{t['ok']} coinciden · {t['diff']} con diferencia · {t['missing']} no están en VozLeads"),
        ("Qué hacer", "Abre Costes → Comparar con Zadarma para ver qué llamadas no cuadran.")],
        every_hours=24, cta=f"{vapi.public_url()}/app/costes", cta_label="Ver comparación")
    return {"sent": sent, "error": "", "totals": t}


@router.post("/admin/costs/zadarma-weekly")
async def run_weekly(user=Depends(require_admin)):
    return await weekly_check(force=True)


async def loop() -> None:
    await asyncio.sleep(90)
    while True:
        try:
            await weekly_check()
        except Exception as e:  # noqa: BLE001
            log.warning("Weekly Zadarma check failed: %s", e)
        await asyncio.sleep(900)
