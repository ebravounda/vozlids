from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

import costs_real as CR
import zadarma as Z
from db import db
from extra_routes import _parts, get_pricing, require_admin

router = APIRouter(prefix="/api")


def _num(v) -> float:
    try:
        return float(str(v or 0).replace(",", "."))
    except ValueError:
        return 0.0


def _when(r: dict):
    try:
        return datetime.strptime(str(r["callstart"])[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CR.MADRID)
    except (KeyError, ValueError, TypeError):
        return None


@router.get("/admin/costs/zadarma-compare")
async def zadarma_compare(days: int = 30, user=Depends(require_admin)):
    pricing = await get_pricing()
    since = datetime.now(timezone.utc) - timedelta(days=max(1, min(days, 29)))
    try:
        stats = await CR._stats(since)
    except Z.ZadarmaError as e:
        return {"rows": [], "totals": {}, "error": str(e)}
    leads = await db.leads.find({"vapi_call_id": {"$ne": None}, "created_at": {"$gte": since.isoformat()}},
                                {"messages": 0, "transcript": 0}).to_list(5000)
    agent_country = {str(a["_id"]): a.get("country", "ES") async for a in db.agents.find({}, {"country": 1})}
    users = {str(u["_id"]): u.get("business_name") or u.get("email") async for u in db.users.find({}, {"business_name": 1, "email": 1})}
    rates = {"ES": pricing["line_rate_usd_min"], "CL": pricing["line_rate_cl_usd_min"]}
    by_num: dict = {}
    for ld in leads:
        by_num.setdefault(CR._digits(ld.get("phone") or "")[-9:], []).append(ld)
    used, rows = set(), []
    t = {"zadarma": 0.0, "panel": 0.0, "zadarma_seconds": 0, "panel_seconds": 0, "ok": 0, "diff": 0, "missing": 0, "free": 0}
    for r in stats:
        when = _when(r)
        cost = CR.to_usd(_num(r.get("billcost")), r.get("currency"), pricing)
        secs = int(_num(r.get("billseconds")))
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
        country = agent_country.get(ld["agent_id"], "ES") if ld else "ES"
        rate = rates.get(country, rates["ES"])
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
