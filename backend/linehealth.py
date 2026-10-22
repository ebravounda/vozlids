"""Every 30 minutes: check each connected line in Zadarma and Vapi; email the admin when one goes down and when it comes back."""
import asyncio
import logging
import os
from datetime import date

import httpx

import emailer
import vapi
import zadarma as Z
from db import db
from models import now_iso

log = logging.getLogger(__name__)
EVERY = 1800
OFF = {"off", "blocked", "disabled", "expired", "deleted", "inactive"}


async def _vapi_ok(phone_id: str) -> bool:
    async with httpx.AsyncClient(timeout=20) as x:
        r = await x.get(f"{vapi.VAPI_URL}/phone-number/{phone_id}", headers=vapi._headers())
    if r.status_code >= 500:
        raise RuntimeError(f"Vapi {r.status_code}")
    return r.status_code < 400


def _digits(n) -> str:
    return "".join(ch for ch in str(n or "") if ch.isdigit())


async def problems(r: dict, nums: dict, sips: set) -> list:
    out = []
    z = nums.get(_digits(r["number"]))
    if z is None:
        out.append("el número ya no está en tu Zadarma")
    else:
        stop = str(z.get("stop_date") or "")[:10]
        if str(z.get("status", "")).lower() in OFF or (stop and stop < date.today().isoformat()):
            out.append("el número está inactivo o vencido en Zadarma")
    if r.get("sip_id") and str(r["sip_id"]) not in sips:
        out.append(f"la línea SIP {r['sip_id']} ya no existe en Zadarma")
    if not r.get("phone_number_id"):
        out.append("no está conectado a la IA: no puede hacer llamadas")
    elif not await _vapi_ok(r["phone_number_id"]):
        out.append("la conexión con la IA (Vapi) se borró: no puede recibir ni hacer llamadas")
    return out


async def _notify(r: dict, down: bool, reasons: list) -> None:
    admin = await db.users.find_one({"role": "admin"}, {"email": 1})
    if not admin:
        return
    link = os.environ["APP_PUBLIC_URL"].rstrip("/") + "/app/lineas"
    if down:
        await emailer.send(admin["email"], f"Línea caída: {r['number']}", f"La línea {r['number']} ha dejado de funcionar",
                           [("Número", r["number"]), ("Problema", "; ".join(reasons)),
                            ("Qué hacer", "Abre Líneas y pulsa «Reconfigurar» en ese número.")], link, cta_label="Abrir Líneas")
    else:
        await emailer.send(admin["email"], f"Línea recuperada: {r['number']}", f"La línea {r['number']} vuelve a funcionar",
                           [("Número", r["number"]), ("Estado", "Recibe y hace llamadas con normalidad")], link, cta_label="Abrir Líneas")


async def check_once() -> list:
    if not (await Z.creds()).get("key") or not os.environ.get("VAPI_API_KEY"):
        return []
    try:
        nums = {_digits(n.get("number")): n for n in await Z.my_numbers()}
        sips = {str(s["id"]) for s in (await Z.list_sips())[0]}
    except Z.ZadarmaError as e:
        log.warning("Line health: Zadarma unavailable: %s", e)
        return []
    out = []
    async for r in db.tenant_numbers.find({"status": "activo", "number": {"$nin": [None, ""]}}):
        try:
            reasons = await problems(r, nums, sips)
        except Exception as e:  # noqa: BLE001 — provider hiccup: skip this round, never false alarms
            log.warning("Line health check failed for %s: %s", r["number"], e)
            continue
        down = bool(reasons)
        was_down = r.get("health") == "caida"
        await db.tenant_numbers.update_one({"_id": r["_id"]}, {"$set": {
            "health": "caida" if down else "ok", "health_reason": "; ".join(reasons), "health_at": now_iso()}})
        if down != was_down:
            await _notify(r, down, reasons)
        out.append({"number": r["number"], "ok": not down, "reasons": reasons})
    return out


async def loop() -> None:
    await asyncio.sleep(120)
    while True:
        try:
            await check_once()
            import vapi_monitor
            await vapi_monitor.auto_repair()
        except Exception as e:  # noqa: BLE001
            log.warning("Line health loop failed: %s", e)
        await asyncio.sleep(EVERY)
