import logging
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

import zadarma as Z
from db import db

log = logging.getLogger("vozlead.costs")
MADRID = ZoneInfo("Europe/Madrid")
SYNC_EVERY_MIN = 10


def _digits(p: str) -> str:
    return re.sub(r"\D", "", p or "")


def _parse(ts: str):
    try:
        return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def to_usd(amount: float, currency: str, pricing: dict) -> float:
    cur = (currency or "USD").upper()
    if cur == "EUR":
        return amount / pricing["usd_eur"]
    if cur == "CLP":
        return amount / pricing["usd_clp"]
    return amount


def eleven_cost(chars: int, pricing: dict) -> float:
    """What the characters spoken cost on your own ElevenLabs plan (Vapi reports 0 for own-key voices)."""
    per_credit = pricing["eleven_plan_usd"] / max(1, pricing["eleven_plan_credits"])
    return chars * pricing["eleven_credits_per_char"] * per_credit


async def _stats(start: datetime) -> list:
    rows, skip = [], 0
    params = {"start": start.astimezone(MADRID).strftime("%Y-%m-%d %H:%M:%S"),
              "end": datetime.now(MADRID).strftime("%Y-%m-%d %H:%M:%S")}
    for _ in range(3):
        page = (await Z.call("GET", "/v1/statistics/", {**params, "skip": skip, "limit": 1000})).get("stats") or []
        rows += page
        if len(page) < 1000:
            break
        skip += 1000
    return rows


async def sync_zadarma(pricing: dict, force: bool = False) -> dict:
    """Store the real Zadarma cost (billcost) on each call, matching by number and start time."""
    st = await db.platform_settings.find_one({"_id": "zadarma_sync"}) or {}
    last = _parse(st.get("at", ""))
    if not force and last and datetime.now(timezone.utc) - last < timedelta(minutes=SYNC_EVERY_MIN):
        return {"skipped": True, **{k: st.get(k) for k in ("matched", "error")}}
    since = datetime.now(timezone.utc) - timedelta(days=29)
    leads = await db.leads.find({"vapi_call_id": {"$ne": None}, "line_cost_usd": None, "duration_seconds": {"$gt": 0},
                                 "created_at": {"$gte": since.isoformat()}},
                                {"phone": 1, "created_at": 1, "started_at": 1, "direction": 1, "source": 1}).to_list(3000)
    out = {"at": datetime.now(timezone.utc).isoformat(), "matched": 0, "pending": len(leads), "error": ""}
    if leads:
        try:
            rows = await _stats(since)
        except Z.ZadarmaError as e:
            out["error"] = str(e)
            rows = []
        by_num: dict = {}
        for r in rows:
            try:
                t = datetime.strptime(str(r["callstart"])[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=MADRID)
            except (KeyError, ValueError, TypeError):
                continue
            for n in {_digits(str(r.get("to") or "")), _digits(str(r.get("from") or ""))} - {""}:
                by_num.setdefault(n[-9:], []).append((t, r))
        used = set()
        for ld in leads:
            start = _parse(ld.get("started_at") or ld.get("created_at"))
            if start is None:
                continue
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
            best = None
            for t, r in by_num.get(_digits(ld.get("phone") or "")[-9:], []):
                if r.get("id") in used:
                    continue
                gap = abs((t - start).total_seconds())
                if gap <= 600 and (best is None or gap < best[0]):
                    best = (gap, r)
            if best:
                r = best[1]
                used.add(r.get("id"))
                try:
                    usd = to_usd(float(str(r.get("billcost") or 0).replace(",", ".")), r.get("currency"), pricing)
                except ValueError:
                    continue
                await db.leads.update_one({"_id": ld["_id"]}, {"$set": {"line_cost_usd": round(usd, 5),
                                                                         "line_currency": r.get("currency")}})
                out["matched"] += 1
        out["pending"] -= out["matched"]
    await db.platform_settings.update_one({"_id": "zadarma_sync"}, {"$set": out}, upsert=True)
    return out


async def eleven_usage() -> dict | None:
    doc = await db.platform_settings.find_one({"_id": "elevenlabs"}) or {}
    key = doc.get("api_key")
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=15) as x:
            r = await x.get("https://api.elevenlabs.io/v1/user/subscription", headers={"xi-api-key": key})
        if r.status_code >= 400:
            return None
        s = r.json()
        return {"tier": s.get("tier"), "used": s.get("character_count"), "limit": s.get("character_limit"),
                "reset_unix": s.get("next_character_count_reset_unix")}
    except httpx.HTTPError:
        return None


async def tenant_revenue(pricing: dict) -> dict:
    """Monthly subscription price of every paying tenant, in USD."""
    plans = {str(p["_id"]): p async for p in db.plans.find({})}
    out = {}
    async for u in db.users.find({"billing_status": "active", "plan_id": {"$ne": None}},
                                 {"plan_id": 1, "country": 1, "billing_test": 1}):
        p = plans.get(str(u["plan_id"]))
        if not p:
            continue
        cl = u.get("country") == "CL"
        price = to_usd(p["price_clp"] if cl else p["price_eur"], "CLP" if cl else "EUR", pricing)
        out[str(u["_id"])] = {"plan": p["name"], "price_usd": price, "test": bool(u.get("billing_test"))}
    return out


async def numbers_by_tenant() -> dict:
    """tenant_id -> list of (country, is_extra) for every active number."""
    out: dict = {}
    async for n in db.tenant_numbers.find({"status": "activo", "platform": {"$ne": True}}, {"tenant_id": 1, "country": 1, "extra": 1}):
        out.setdefault(n["tenant_id"], []).append((n.get("country", "ES"), bool(n.get("extra"))))
    return out
