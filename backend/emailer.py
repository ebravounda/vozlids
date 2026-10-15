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


FONT = "'Helvetica Neue',Helvetica,Arial,sans-serif"


def _wrap(title: str, rows: list, cta: str = "", intro: str = "", cta_label: str = "Abrir mi panel") -> str:
    site = os.environ["APP_PUBLIC_URL"].rstrip("/")
    e = lambda v: escape(str(v))  # noqa: E731
    items = "".join(
        f'<tr><td style="padding:14px 0;border-bottom:1px solid #EEF2F7;color:#64748B;font-size:13px;width:38%;vertical-align:top">{e(k)}</td>'
        f'<td style="padding:14px 0 14px 12px;border-bottom:1px solid #EEF2F7;color:#0B1B3F;font-size:15px;font-weight:600;vertical-align:top">{e(v)}</td></tr>'
        for k, v in rows if v)
    lead = f'<p style="margin:0 0 24px;color:#475569;font-size:15px;line-height:24px">{e(intro)}</p>' if intro else ""
    button = (f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:32px 0 4px"><tr>'
              f'<td style="border-radius:999px;background:#1E5EFF"><a href="{e(cta)}" style="display:inline-block;padding:14px 30px;'
              f'font-family:{FONT};font-size:15px;font-weight:700;color:#FFFFFF;text-decoration:none;border-radius:999px">{e(cta_label)} &rarr;</a></td>'
              f'</tr></table>') if cta else ""
    legal = " &middot; ".join(f'<a href="{site}{p}" style="color:#94A3B8;text-decoration:underline">{t}</a>'
                              for p, t in (("/terminos", "Términos"), ("/privacidad", "Privacidad"), ("/cookies", "Cookies")))
    return (
        f'<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta name="color-scheme" content="light only"><title>{e(title)}</title></head>'
        f'<body style="margin:0;padding:0;background:#F1F5FB">'
        f'<div style="display:none;max-height:0;overflow:hidden;opacity:0">{e(intro or title)}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F1F5FB"><tr><td align="center" style="padding:32px 12px">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;font-family:{FONT}">'
        f'<tr><td style="padding:0 8px 20px"><a href="{site}" style="text-decoration:none">'
        f'<img src="{site}/brand/vozleads-logo.png" width="150" height="35" alt="VozLeads" style="display:block;border:0;width:150px;height:auto"></a></td></tr>'
        f'<tr><td style="background:#FFFFFF;border-radius:20px;overflow:hidden;box-shadow:0 1px 3px rgba(11,27,63,.06)">'
        f'<div style="height:6px;background:#1E5EFF;background-image:linear-gradient(90deg,#1E5EFF,#10B981)"></div>'
        f'<div style="padding:40px 40px 36px">'
        f'<h1 style="margin:0 0 14px;color:#0B1B3F;font-size:26px;line-height:34px;font-weight:800;letter-spacing:-0.4px">{e(title)}</h1>'
        f'{lead}<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #EEF2F7">{items}</table>{button}'
        f'</div></td></tr>'
        f'<tr><td style="padding:28px 8px 0;color:#94A3B8;font-size:12px;line-height:19px">'
        f'<p style="margin:0 0 8px">Tu asistente telefónico con IA · Nunca te pediremos contraseñas ni datos de pago por email.</p>'
        f'<p style="margin:0 0 8px">VozLeads es parte del Grupo GoRoky · GoRoky LLC · Estados Unidos, España, Chile<br>'
        f'Raimundo Fernández Villaverde 39, Madrid, España · <a href="mailto:soporte@goroky.com" style="color:#94A3B8">soporte@goroky.com</a></p>'
        f'<p style="margin:0">{legal}</p></td></tr>'
        f'</table></td></tr></table></body></html>')


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


async def send(to: str, subject: str, title: str, rows: list, cta: str = "", intro: str = "",
               cta_label: str = "Abrir mi panel") -> bool:
    if not to:
        return False
    err = await deliver(to, subject, _wrap(title, rows, cta, intro, cta_label))
    if err:
        log.warning("Email not sent to %s: %s", to, err)
    return not err
