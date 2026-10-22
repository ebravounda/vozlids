"""Per-plan features and limits (super admin configures them on each plan)."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from bson import ObjectId
from fastapi import HTTPException
from pydantic import BaseModel, Field
from db import db

FEATURES = {
    "outbound": "las llamadas salientes",
    "api": "la API para desarrolladores",
    "widget": "el botón para tu web",
    "agenda_pro": "Google Calendar y los recordatorios de citas",
    "multilang": "la atención en varios idiomas",
    "ambience": "el ambiente de oficina de fondo",
    "dialer": "el teléfono en el panel",
}
DEFAULT = {"max_agents": 0, "max_concurrent": 0, "recording_days": 0, **{k: True for k in FEATURES}}
LIVE = ("llamando", "en_curso")


class LimitsIn(BaseModel):
    max_agents: int = Field(0, ge=0, le=1000)
    max_concurrent: int = Field(0, ge=0, le=500)
    recording_days: int = Field(0, ge=0, le=3650)
    outbound: bool = True
    api: bool = True
    widget: bool = True
    agenda_pro: bool = True
    multilang: bool = False
    ambience: bool = True
    dialer: bool = False


async def for_tenant(tid: str) -> dict:
    u = await db.users.find_one({"_id": ObjectId(tid)}, {"plan_id": 1, "role": 1}) if ObjectId.is_valid(tid) else None
    if not u or u.get("role") == "admin" or not u.get("plan_id") or not ObjectId.is_valid(u["plan_id"]):
        return dict(DEFAULT)
    plan = await db.plans.find_one({"_id": ObjectId(u["plan_id"])}, {"limits": 1}) or {}
    return {**DEFAULT, "multilang": False, "dialer": False, **(plan.get("limits") or {})}


def locked(feature: str) -> HTTPException:
    return HTTPException(403, f"Tu plan no incluye {FEATURES[feature]}. Puedes mejorarlo en «Mi plan».")


async def require(tid: str, feature: str) -> None:
    if not (await for_tenant(tid))[feature]:
        raise locked(feature)


async def has(tid: str, feature: str) -> bool:
    return bool((await for_tenant(tid))[feature])


async def concurrency_error(tid: str) -> Optional[str]:
    lim = (await for_tenant(tid))["max_concurrent"]
    if not lim:
        return None
    recent = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    live = await db.leads.count_documents({"tenant_id": tid, "status": {"$in": list(LIVE)}, "updated_at": {"$gte": recent}})
    return f"Tu plan permite {lim} {'llamada' if lim == 1 else 'llamadas'} a la vez y ya están en curso." if live >= lim else None


async def check_agent(tid: str, voice: str, ambience: str, new: bool) -> None:
    import vapi
    lim = await for_tenant(tid)
    if new and lim["max_agents"] and await db.agents.count_documents({"tenant_id": tid}) >= lim["max_agents"]:
        n = lim["max_agents"]
        raise HTTPException(403, f"Tu plan permite {n} {'agente' if n == 1 else 'agentes'}. Mejora tu plan en «Mi plan» para crear más.")
    if not lim["ambience"] and ambience != "none":
        raise locked("ambience")


async def effective_agent(agent: dict) -> dict:
    """Downgrade voice/ambience at call time when the tenant's current plan no longer includes them."""
    import vapi
    lim = await for_tenant(agent["tenant_id"])
    out = dict(agent)
    if not lim["multilang"]:
        out["languages"] = []
    if not lim["ambience"]:
        out["ambience"] = "none"
    return out
