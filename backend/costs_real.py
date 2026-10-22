import logging
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
import phonenumbers

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


def region(phone: str) -> str | None:
    raw = (phone or "").strip()
    if not (raw.startswith("+") or raw.startswith("00") or len(_digits(raw)) > 9):
        return None
    try:
        return phonenumbers.region_code_for_number(phonenumbers.parse("+" + _digits(raw).removeprefix("00")))
    except phonenumbers.NumberParseException:
        return None


def line_rate(phone: str, agent_country: str, pricing: dict) -> float:
    """Per-minute line cost: own tariff for ES/CL, learned Zadarma tariff for other destinations."""
    base = {"ES": pricing["line_rate_usd_min"], "CL": pricing["line_rate_cl_usd_min"]}
    reg = region(phone)
    if reg in base:
        return base[reg]
    learned = (pricing.get("dest_rates") or {}).get(reg or "")
    return learned["usd_min"] if learned and "usd_min" in learned else base.get(agent_country, base["ES"])


async def learn_rates(rows: list, pricing: dict) -> int:
    """Store the per-minute price Zadarma charged for each foreign destination (manual values are kept)."""
    doc = await db.platform_settings.find_one({"_id": "dest_rates"}) or {}
    known, upd = doc.get("rates") or {}, {}
    for r in rows:
        secs = _num(r.get("billseconds"))
        cost = _num(r.get("billcost"))
        reg = region("+" + _digits(str(r.get("to") or "")))
        if not reg or reg in ("ES", "CL") or secs <= 0 or cost <= 0 or (known.get(reg) or {}).get("manual"):
            continue
        per_min = _num(r.get("cost")) or cost / secs * 60
        usd = round(to_usd(per_min, r.get("currency"), pricing), 4)
        if (known.get(reg) or {}).get("usd_min") != usd:
            upd[f"rates.{reg}"] = {"usd_min": usd, "name": str(r.get("description") or reg)[:60], "manual": False,
                                   "learned_at": datetime.now(timezone.utc).isoformat()}
            known[reg] = upd[f"rates.{reg}"]
    if upd:
        await db.platform_settings.update_one({"_id": "dest_rates"}, {"$set": upd}, upsert=True)
    return len(upd)


def _num(v) -> float:
    try:
        return float(str(v or 0).replace(",", "."))
    except ValueError:
        return 0.0


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


def _row_time(r: dict):
    try:
        return datetime.strptime(str(r["callstart"])[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=MADRID)
    except (KeyError, ValueError, TypeError):
        return None


def match(leads: list, rows: list, taken: set | None = None) -> dict:
    """Pair VozLeads calls with Zadarma records: same number, closest start time and most similar duration, each record used once."""
    by_num: dict = {}
    for r in rows:
        t = _row_time(r)
        if t is None or str(r.get("id")) in (taken or set()):
            continue
        for n in {_digits(str(r.get("to") or ""))[-9:], _digits(str(r.get("from") or ""))[-9:]} - {""}:
            by_num.setdefault(n, []).append((t, r))
    pairs = []
    for ld in leads:
        start = _parse(ld.get("started_at") or ld.get("created_at"))
        if start is None:
            continue
        start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
        secs = ld.get("duration_seconds") or 0
        for t, r in by_num.get(_digits(ld.get("phone") or "")[-9:], []):
            gap = abs((t - start).total_seconds())
            if gap <= 600:
                pairs.append((gap + 2 * abs(_num(r.get("billseconds")) - secs), str(ld["_id"]), str(r.get("id")), r))
    out, used = {}, set()
    for _, lid, rid, r in sorted(pairs, key=lambda p: p[0]):
        if lid not in out and rid not in used:
            out[lid] = r
            used.add(rid)
    return out


async def sync_zadarma(pricing: dict, force: bool = False) -> dict:
    """Store the real Zadarma cost (billcost) on each call."""
    st = await db.platform_settings.find_one({"_id": "zadarma_sync"}) or {}
    last = _parse(st.get("at", ""))
    if not force and last and datetime.now(timezone.utc) - last < timedelta(minutes=SYNC_EVERY_MIN):
        return {"skipped": True, **{k: st.get(k) for k in ("matched", "error")}}
    since = datetime.now(timezone.utc) - timedelta(days=29)
    base = {"vapi_call_id": {"$ne": None}, "created_at": {"$gte": since.isoformat()}}
    leads = await db.leads.find({**base, "line_zadarma_id": None, "duration_seconds": {"$gt": 0}},
                                {"phone": 1, "created_at": 1, "started_at": 1, "duration_seconds": 1}).to_list(3000)
    out = {"at": datetime.now(timezone.utc).isoformat(), "matched": 0, "pending": len(leads), "error": ""}
    if leads:
        try:
            rows = await _stats(since)
        except Z.ZadarmaError as e:
            out["error"] = str(e)
            rows = []
        import dialer
        manual = await dialer.manual_ids()
        rows = [r for r in rows if str(r.get("id")) not in manual]
        await learn_rates(rows, pricing)
        taken = {d["line_zadarma_id"] async for d in db.leads.find({**base, "line_zadarma_id": {"$ne": None}}, {"line_zadarma_id": 1})}
        ids = {str(ld["_id"]): ld["_id"] for ld in leads}
        for lid, r in match(leads, rows, taken).items():
            usd = to_usd(_num(r.get("billcost")), r.get("currency"), pricing)
            await db.leads.update_one({"_id": ids[lid]}, {"$set": {"line_cost_usd": round(usd, 5), "line_currency": r.get("currency"),
                                                                  "line_zadarma_id": str(r.get("id"))}})
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
