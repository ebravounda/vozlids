# Iter41: Super admin Vapi monitor (read-only GET endpoints only — never call repair/reconfigure)
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    if r.status_code != 200:
        pytest.skip("admin login failed")
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def user():
    s = requests.Session()
    e = f"test_vm_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={"name": "TEST VM", "business_name": "TEST_VM", "email": e, "password": "Test12345!"}, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"register failed {r.status_code} {r.text[:200]}")
    tok = r.json().get("access_token")
    if tok:
        s.headers["Authorization"] = f"Bearer {tok}"
    return s


EPS = ["calls", "errors", "spend", "numbers"]


@pytest.mark.parametrize("ep", EPS)
def test_unauth_rejected(ep):
    r = requests.get(f"{BASE_URL}/api/admin/vapi/{ep}", timeout=30)
    assert r.status_code in (401, 403)


@pytest.mark.parametrize("ep", EPS)
def test_non_admin_forbidden(user, ep):
    r = user.get(f"{BASE_URL}/api/admin/vapi/{ep}", timeout=30)
    assert r.status_code in (401, 403)


def test_calls(admin):
    r = admin.get(f"{BASE_URL}/api/admin/vapi/calls", timeout=90)
    assert r.status_code == 200, r.text[:300]
    rows = r.json()
    assert isinstance(rows, list)
    print("calls:", len(rows))
    keys = {"id", "at", "direction", "number", "owner", "customer", "seconds", "cost", "reason", "level", "code"}
    for row in rows:
        assert keys <= set(row)
        assert row["level"] in ("ok", "aviso", "error")
        assert row["direction"] in ("entrante", "saliente", "web")
        assert isinstance(row["seconds"], int)
        assert isinstance(row["cost"], (int, float))
    if rows:
        print("sample:", {k: rows[0][k] for k in keys})


def test_errors(admin):
    r = admin.get(f"{BASE_URL}/api/admin/vapi/errors", timeout=90)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert isinstance(d["calls"], list) and isinstance(d["events"], list)
    assert all(c["level"] == "error" for c in d["calls"])
    assert all("_id" not in e for e in d["events"])
    print("errors:", len(d["calls"]), "events:", len(d["events"]))


def test_spend(admin):
    r = admin.get(f"{BASE_URL}/api/admin/vapi/spend", timeout=120)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert isinstance(d["days"], list) and isinstance(d["owners"], list)
    assert len(d["days"]) <= 15
    for x in d["days"]:
        assert {"day", "calls", "minutes", "cost"} <= set(x)
    for x in d["owners"]:
        assert {"owner", "calls", "minutes", "cost"} <= set(x)
    assert [x["day"] for x in d["days"]] == sorted(x["day"] for x in d["days"])
    costs = [x["cost"] for x in d["owners"]]
    assert costs == sorted(costs, reverse=True)
    print("days:", d["days"][-3:], "owners:", d["owners"][:3])


def test_numbers(admin):
    r = admin.get(f"{BASE_URL}/api/admin/vapi/numbers", timeout=90)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    for k in ("shared", "transfer_ready", "duplicates", "zadarma", "numbers", "webhook"):
        assert k in d
    assert isinstance(d["numbers"], list)
    for n in d["numbers"]:
        assert {"number", "owner", "alias", "issues", "ok"} <= set(n)
        assert n["ok"] == (not n["issues"])
    print({k: d[k] for k in ("shared", "transfer_ready", "duplicates", "zadarma", "webhook")}, d["numbers"])


def test_reason_mapping_unit():
    import sys
    sys.path.insert(0, "/app/backend")
    try:
        import vapi_monitor as VM
    except Exception as e:
        pytest.skip(f"import failed: {e}")
    assert VM.reason("customer-ended-call", "") == ("El cliente colgó", "ok")
    assert VM.reason("", "")[0] == "En curso"
    assert VM.reason("call.in-progress.error-sip-trunk-failed", "")[1] == "error"
    assert VM.reason("pipeline-error-openai-llm-failed", "")[1] == "error"
    assert VM.reason("x", "Hola, gracias por llamar. Ahora mismo no podemos atender")[1] == "error"
    assert VM.reason("weird-code", "") == ("weird-code", "aviso")
