import os
import requests

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
APP_NAME = "vozlead"
_key = None


def init_storage(force: bool = False) -> str:
    global _key
    if _key and not force:
        return _key
    r = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": os.environ["EMERGENT_LLM_KEY"]}, timeout=30)
    r.raise_for_status()
    _key = r.json()["storage_key"]
    return _key


def _request(method: str, path: str, **kw):
    for attempt in (0, 1):
        r = requests.request(method, f"{STORAGE_URL}/objects/{path}",
                             headers={"X-Storage-Key": init_storage(force=attempt == 1), **kw.pop("headers", {})},
                             timeout=120, **kw)
        if r.status_code != 404 or attempt:
            r.raise_for_status()
            return r


def put_object(path: str, data: bytes, content_type: str) -> dict:
    return _request("PUT", path, data=data, headers={"Content-Type": content_type}).json()


def get_object(path: str) -> bytes:
    return _request("GET", path).content
