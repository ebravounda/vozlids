import base64
import hashlib
import hmac
from urllib.parse import urlencode
import httpx
from db import db

BASE = "https://api.zadarma.com"


class ZadarmaError(Exception):
    pass


async def creds() -> dict:
    return (await db.platform_settings.find_one({"_id": "zadarma_api"})) or {}


def _sign(method: str, params: dict, key: str, secret: str) -> str:
    qs = urlencode(sorted(params.items()))
    data = method + qs + hashlib.md5(qs.encode()).hexdigest()
    digest = hmac.new(secret.encode(), data.encode(), hashlib.sha1).hexdigest()
    return f"{key}:{base64.b64encode(digest.encode()).decode()}"


async def call(verb: str, method: str, params: dict | None = None, key: str = "", secret: str = "") -> dict:
    if not key:
        c = await creds()
        key, secret = c.get("key", ""), c.get("secret", "")
    if not key:
        raise ZadarmaError("Falta conectar la API de Zadarma en Super admin.")
    params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
    headers = {"Authorization": _sign(method, params, key, secret)}
    qs = urlencode(sorted(params.items()))
    try:
        async with httpx.AsyncClient(timeout=30) as x:
            if verb == "GET":
                r = await x.get(f"{BASE}{method}" + (f"?{qs}" if qs else ""), headers=headers)
            else:
                r = await x.request(verb, f"{BASE}{method}", content=qs, headers={
                    **headers, "Content-Type": "application/x-www-form-urlencoded"})
    except httpx.HTTPError as e:
        raise ZadarmaError(f"No se pudo contactar con Zadarma: {e.__class__.__name__}")
    try:
        data = r.json()
    except ValueError:
        raise ZadarmaError(f"Zadarma respondió {r.status_code}: {r.text[:200]}")
    if r.status_code >= 400 or data.get("status") != "success":
        raise ZadarmaError(f"Zadarma: {data.get('message') or data.get('error') or r.text[:200]}")
    return data


async def balance(key: str = "", secret: str = "") -> dict:
    return await call("GET", "/v1/info/balance/", key=key, secret=secret)


async def directions(country: str) -> list:
    return (await call("GET", "/v1/direct_numbers/country/", {"country": country, "language": "es"})).get("info", [])


async def document_groups() -> list:
    try:
        d = await call("GET", "/v1/documents/groups/list/")
    except ZadarmaError:
        return []
    return d.get("groups") or d.get("info") or []


async def create_group(data: dict) -> str:
    res = await call("POST", "/v1/documents/groups/create/", data)
    return str((res.get("group") or {}).get("id", ""))


async def upload_doc(group_id: str, doc_type: str, content: bytes, filename: str, mime: str) -> None:
    c = await creds()
    params = {"document_type": doc_type, "group_id": group_id}
    headers = {"Authorization": _sign("/v1/documents/upload/", params, c["key"], c["secret"])}
    try:
        async with httpx.AsyncClient(timeout=60) as x:
            r = await x.post(f"{BASE}/v1/documents/upload/", data=params, files={"file": (filename, content, mime)}, headers=headers)
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise ZadarmaError(f"No se pudo subir el documento a Zadarma: {e.__class__.__name__}")
    if data.get("status") != "success":
        raise ZadarmaError(f"Zadarma: {data.get('message') or r.text[:200]}")


async def group_valid(group_id: str, direction_id: str) -> dict:
    return await call("GET", f"/v1/documents/groups/valid/{group_id}/", {"direction_id": direction_id})


async def order(direction_id: str, documents_group_id: str = "") -> str:
    avail = (await call("GET", f"/v1/direct_numbers/available/{direction_id}/")).get("numbers") or []
    params = {"direction_id": direction_id, "documents_group_id": documents_group_id, "period": "month",
              "autorenew_period": "month"}
    if avail:
        params["number_id"] = avail[0]["id"]
    res = await call("POST", "/v1/direct_numbers/order/", params)
    return "+" + str(res["number"]).lstrip("+")


async def my_numbers() -> list:
    return (await call("GET", "/v1/direct_numbers/")).get("info") or []


async def create_sip(name: str, password: str, callerid: str) -> str:
    return str((await call("POST", "/v1/sip/create/", {"name": name[:30], "password": password,
                                                        "callerid": callerid.lstrip("+")}))["sip"])


async def route_to(number: str, sip_uri: str) -> None:
    await call("PUT", "/v1/direct_numbers/set_sip_id/", {"number": number.lstrip("+"), "sip_id": sip_uri})


async def autorenew(number: str, on: bool) -> None:
    await call("PUT", "/v1/direct_numbers/autoprolongation/", {"number": number.lstrip("+"), "value": "on" if on else "off"})
