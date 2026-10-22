"""Daily jobs: payment reminder 3 days before each Stripe renewal, and monthly AI re-read of each agent's website (suggestions only)."""
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import stripe
from bson import ObjectId
from emergentintegrations.llm.chat import LlmChat, UserMessage
from fastapi import APIRouter, Depends, HTTPException

import billing as B
import emailer
import webscan as W
from auth import get_current_user
from db import db
from models import now_iso

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
DAY = 86400
NO_CHANGES = "SIN CAMBIOS"
DIFF_PROMPT = ("Comparas la información guardada de un negocio con el texto actual de su web. Escribe en español SOLO lo que ha cambiado o es "
               "nuevo y relevante para atender llamadas (precios, horarios, servicios, dirección, contacto, políticas), en frases cortas con guiones. "
               f"Si no hay cambios relevantes responde exactamente: {NO_CHANGES}. No inventes nada.")


def _money(amount: int, cur: str) -> str:
    return f"{amount:,} CLP".replace(",", ".") if cur == "clp" else f"{amount / 100:.2f} {cur.upper()}".replace(".", ",")


async def payment_reminders() -> int:
    sent = 0
    now = datetime.now(timezone.utc).timestamp()
    for mode in ("live", "test"):
        c, s, proxy = await B.client(mode)
        if proxy or (mode == "test" and not s.get("test_key")):
            continue
        try:
            subs = await asyncio.to_thread(c.v1.subscriptions.list, {"limit": 100, "status": "active"})
        except stripe.error.StripeError as e:
            log.warning("Payment reminders (%s): %s", mode, e)
            continue
        for sub in subs.data:
            items = (sub.get("items") or {}).get("data") or []
            end = sub.get("current_period_end") or (items[0].get("current_period_end") if items else 0)
            if sub.get("cancel_at_period_end") or not end or not (2 * DAY < end - now <= 3 * DAY):
                continue
            u = await db.users.find_one({"stripe_subscription_id": sub["id"]})
            if not u or u.get("reminded_period_end") == end:
                continue
            cur = (items[0].get("price") or {}).get("currency", "eur") if items else "eur"
            total = sum(((i.get("price") or {}).get("unit_amount") or 0) * (i.get("quantity") or 1) for i in items)
            when = datetime.fromtimestamp(end, timezone.utc).strftime("%d/%m/%Y")
            await emailer.send(u["email"], f"Tu plan de VozLeads se renueva el {when}", "Recordatorio de tu próximo cobro", [
                ("Fecha de cobro", when), ("Importe aproximado", _money(total, cur)),
                ("Tarjeta", "Se cobra a la tarjeta guardada. Si ha cambiado, actualízala antes para no cortar tus llamadas.")],
                os.environ["APP_PUBLIC_URL"].rstrip("/") + "/app/plan", "Te avisamos con 3 días de antelación.", "Revisar mi plan y tarjeta")
            await db.users.update_one({"_id": u["_id"]}, {"$set": {"reminded_period_end": end}})
            sent += 1
    return sent


async def refresh_websites() -> int:
    key = await W._key()
    if not key:
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    found = 0
    async for a in db.agents.find({"website": {"$nin": [None, ""]}, "$or": [{"web_checked_at": {"$exists": False}}, {"web_checked_at": {"$lt": cutoff}}]}).limit(50):
        await db.agents.update_one({"_id": a["_id"]}, {"$set": {"web_checked_at": now_iso()}})
        try:
            text, _ = await W.read_site(a["website"])
            chat = LlmChat(api_key=key, session_id=f"webdiff-{a['_id']}-{now_iso()}", system_message=DIFF_PROMPT).with_model("openai", W.MODEL)
            diff = str(await chat.send_message(UserMessage(text=f"GUARDADO:\n{a.get('web_summary') or a.get('product', '')}\n\nWEB ACTUAL ({a['website']}):\n{text}"))).strip()
        except Exception as e:  # noqa: BLE001 — site down / provider error: try again next month
            log.warning("Web refresh failed for agent %s: %s", a["_id"], e)
            continue
        if not diff or NO_CHANGES in diff.upper()[:40]:
            continue
        await db.agents.update_one({"_id": a["_id"]}, {"$set": {"web_suggestion": {"text": diff[:3000], "at": now_iso(), "url": a["website"]}}})
        u = await db.users.find_one({"_id": ObjectId(a["tenant_id"])}, {"email": 1})
        if u:
            await emailer.send(u["email"], f"Tu web ha cambiado: actualiza a {a['name']}", "Hemos encontrado cambios en tu web", [
                ("Agente", a["name"]), ("Web", a["website"]), ("Cambios", diff[:600])],
                os.environ["APP_PUBLIC_URL"].rstrip("/") + f"/app/agentes/{a['_id']}", "Revísalos y añádelos con un clic para que tu agente informe bien.", "Revisar cambios")
        found += 1
    return found


async def loop() -> None:
    await asyncio.sleep(300)
    while True:
        for job in (payment_reminders, refresh_websites):
            try:
                await job()
            except Exception as e:  # noqa: BLE001
                log.warning("Daily job %s failed: %s", job.__name__, e)
        await asyncio.sleep(6 * 3600)


async def _own(agent_id: str, user: dict) -> dict:
    a = await db.agents.find_one({"_id": ObjectId(agent_id), "tenant_id": user["id"]}) if ObjectId.is_valid(agent_id) else None
    if not a or not a.get("web_suggestion"):
        raise HTTPException(404, "No hay cambios pendientes.")
    return a


@router.post("/agents/{agent_id}/web-suggestion/apply")
async def apply_suggestion(agent_id: str, user=Depends(get_current_user)):
    a = await _own(agent_id, user)
    s = a["web_suggestion"]
    product = f"{a.get('product', '').rstrip()}\n\n— Cambios de la web ({s['at'][:10]}) —\n{s['text']}".strip()
    if len(product) > 8000:
        raise HTTPException(409, "No cabe: la información del negocio superaría 8000 caracteres. Acórtala y vuelve a intentarlo.")
    await db.agents.update_one({"_id": a["_id"]}, {"$set": {"product": product, "web_summary": f"{a.get('web_summary', '')}\n{s['text']}"[-4000:],
                                                            "updated_at": now_iso()}, "$unset": {"web_suggestion": ""}})
    return {"ok": True, "product": product}


@router.post("/agents/{agent_id}/web-suggestion/dismiss")
async def dismiss_suggestion(agent_id: str, user=Depends(get_current_user)):
    a = await _own(agent_id, user)
    await db.agents.update_one({"_id": a["_id"]}, {"$unset": {"web_suggestion": ""}})
    return {"ok": True}
