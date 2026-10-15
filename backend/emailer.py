import ipaddress
import logging
import os
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
import httpx

log = logging.getLogger("vozlead.email")
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")


def _wrap(title: str, rows: list, cta: str = "") -> str:
    brand = escape(os.environ["EMAIL_FROM_NAME"])
    items = "".join(f'<tr><td style="padding:4px 0;color:#64748b;width:140px">{escape(k)}</td>'
                    f'<td style="padding:4px 0;color:#0f172a">{escape(str(v))}</td></tr>' for k, v in rows if v)
    link = (f'<p style="margin-top:20px"><a href="{escape(cta)}" style="background:#059669;color:#fff;padding:10px 18px;'
            f'border-radius:999px;text-decoration:none">Abrir mi panel</a></p>') if cta else ""
    return (f'<table role="presentation" width="100%" style="background:#f8fafc"><tr><td style="padding:24px">'
            f'<table role="presentation" width="560" style="background:#fff;border:1px solid #e2e8f0;border-radius:12px">'
            f'<tr><td style="padding:28px;font-family:Arial,sans-serif">'
            f'<p style="margin:0 0 6px;font-weight:bold;color:#059669">{brand}</p>'
            f'<h2 style="margin:0 0 16px;color:#0f172a;font-size:20px">{escape(title)}</h2>'
            f'<table role="presentation">{items}</table>{link}'
            f'<p style="margin-top:28px;font-size:12px;color:#94a3b8">Enviado por {brand}. Nunca te pediremos contraseñas '
            f'ni datos de pago por email.</p></td></tr></table></td></tr></table>')


async def resend_cfg() -> dict:
    from db import db
    return (await db.platform_settings.find_one({"_id": "resend"})) or {}


def _sender(addr: str) -> str:
    return addr if "<" in addr else f"{os.environ['EMAIL_FROM_NAME']} <{addr.strip()}>"


async def deliver(to: str, subject: str, html: str) -> str:
    """Sends via the admin's Resend account if configured, else the built-in sender. Returns '' or an error."""
    _assert_safe_email(subject, html)
    cfg = await resend_cfg()
    reply = cfg.get("reply_to") or os.environ.get("EMAIL_REPLY_TO")
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            if cfg.get("api_key"):
                payload = {"from": _sender(cfg["from_email"]), "to": [to], "subject": subject, "html": html}
                if reply:
                    payload["reply_to"] = [reply]
                r = await c.post("https://api.resend.com/emails", json=payload, headers={
                    "Authorization": f"Bearer {cfg['api_key']}", "User-Agent": "vozleads/1.0"})
            else:
                payload = {"to": [to], "subject": subject, "html": html, "from_name": os.environ["EMAIL_FROM_NAME"]}
                if reply:
                    payload["contact_email"] = reply
                r = await c.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                 headers={"X-Email-Key": os.environ["EMERGENT_EMAIL_KEY"]}, json=payload)
    except httpx.HTTPError as e:
        return f"No se pudo contactar con el servicio de email: {e.__class__.__name__}"
    if r.status_code >= 400:
        try:
            msg = r.json().get("message") or r.text
        except ValueError:
            msg = r.text
        return f"Error {r.status_code}: {str(msg)[:300]}"
    return ""


async def send(to: str, subject: str, title: str, rows: list, cta: str = "") -> bool:
    if not to:
        return False
    err = await deliver(to, subject, _wrap(title, rows, cta))
    if err:
        log.warning("Email not sent to %s: %s", to, err)
    return not err
