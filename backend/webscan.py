"""Read a business website with AI (super admin's own OpenAI key) and draft the agent's business info. Max 2 scans/day per account."""
import asyncio
import ipaddress
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from emergentintegrations.llm.chat import LlmChat, UserMessage
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from db import db
from extra_routes import require_admin
from models import now_iso

router = APIRouter(prefix="/api")
MODEL = "gpt-5.4-mini"
PER_DAY = 2
KEYWORDS = ("servicio", "precio", "tarifa", "contact", "nosotros", "about", "horario", "faq", "pregunta", "carta", "menu", "producto")
PROMPT = ("Eres un asistente que prepara la información de un negocio para un recepcionista telefónico con IA. Con el texto de su web, "
          "escribe en español un resumen claro y verificable con estos apartados si aparecen: Qué es el negocio, Servicios/productos y precios, "
          "Horarios, Dirección y zona de servicio, Contacto, Formas de pago, Políticas (reservas, cancelaciones, envíos), Preguntas frecuentes. "
          "Usa solo datos que estén en el texto; no inventes nada. Frases cortas, máximo 3000 caracteres, sin markdown con asteriscos.")


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out, self.links, self._skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.out.append(data.strip())


def _public(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    return all(ipaddress.ip_address(i[4][0]).is_global for i in infos)


async def _fetch(x: httpx.AsyncClient, url: str):
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname or not await asyncio.to_thread(_public, p.hostname):
        return None
    try:
        r = await x.get(url)
    except httpx.HTTPError:
        return None
    if r.status_code >= 400 or "html" not in r.headers.get("content-type", ""):
        return None
    t = _Text()
    t.feed(r.text[:1_500_000])
    return " ".join(t.out), [urljoin(str(r.url), h) for h in t.links]


async def read_site(url: str) -> tuple[str, int]:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 VozLeadsBot"}) as x:
        first = await _fetch(x, url)
        if not first:
            raise HTTPException(400, "No se pudo leer esa web. Revisa la dirección (por ejemplo https://tunegocio.com).")
        text, links = first
        host = urlparse(url).hostname
        extra = list(dict.fromkeys(u.split("#")[0] for u in links if urlparse(u).hostname == host and any(k in u.lower() for k in KEYWORDS)))[:4]
        pages = [text] + [r[0] for r in await asyncio.gather(*(_fetch(x, u) for u in extra)) if r]
    return re.sub(r"\s+", " ", "\n\n".join(pages))[:24000], len(pages)


async def _key() -> str:
    return (await db.platform_settings.find_one({"_id": "openai"}) or {}).get("api_key", "")


class KeyIn(BaseModel):
    api_key: str = Field(min_length=20, max_length=300)


@router.get("/admin/openai")
async def openai_status(user=Depends(require_admin)):
    k = await _key()
    return {"connected": bool(k), "hint": f"…{k[-4:]}" if k else "", "model": MODEL, "per_day": PER_DAY}


@router.put("/admin/openai")
async def openai_save(body: KeyIn, user=Depends(require_admin)):
    key = body.api_key.strip()
    try:
        await LlmChat(api_key=key, session_id="vl-key-check", system_message="Responde solo OK.").with_model("openai", MODEL).send_message(UserMessage(text="OK"))
    except Exception as e:  # noqa: BLE001 — surface provider message
        raise HTTPException(400, f"OpenAI rechazó la clave: {str(e)[:200]}")
    await db.platform_settings.update_one({"_id": "openai"}, {"$set": {"api_key": key, "updated_at": now_iso()}}, upsert=True)
    return {"ok": True}


@router.delete("/admin/openai")
async def openai_delete(user=Depends(require_admin)):
    await db.platform_settings.delete_one({"_id": "openai"})
    return {"ok": True}


class ScanIn(BaseModel):
    url: str = Field(min_length=4, max_length=300)


@router.post("/agents/scan-website")
async def scan(body: ScanIn, user=Depends(get_current_user)):
    key = await _key()
    if not key:
        raise HTTPException(409, "La lectura de webs con IA aún no está activada. Escríbenos desde Asistencia técnica.")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    used = await db.web_scans.count_documents({"tenant_id": user["id"], "day": day})
    if used >= PER_DAY and user.get("role") != "admin":
        raise HTTPException(429, f"Ya usaste las {PER_DAY} lecturas de web de hoy. Vuelve a intentarlo mañana.")
    url = body.url.strip()
    url = url if url.startswith(("http://", "https://")) else "https://" + url
    text, pages = await read_site(url)
    if len(text) < 200:
        raise HTTPException(400, "La web tiene muy poco texto para leer (puede estar hecha solo con imágenes).")
    chat = LlmChat(api_key=key, session_id=f"scan-{user['id']}-{now_iso()}", system_message=PROMPT).with_model("openai", MODEL)
    try:
        summary = await chat.send_message(UserMessage(text=f"Web: {url}\n\nTexto:\n{text}"))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(424, f"La IA no pudo leer la web ahora: {str(e)[:160]}")
    await db.web_scans.insert_one({"tenant_id": user["id"], "day": day, "url": url, "pages": pages, "created_at": now_iso()})
    return {"summary": str(summary).strip()[:3500], "pages": pages, "remaining": max(0, PER_DAY - used - 1)}
