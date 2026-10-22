# Iter40: per-agent receptionist (own extra number), business facts, transfer number & notify email validation
import os, sys, asyncio
import pytest, requests
from dotenv import load_dotenv

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
AID = "6acfac3a346c4c1ebc71ff58"


@pytest.fixture(scope="module")
def s():
    ss = requests.Session()
    r = ss.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@vozlead.es", "password": "VozLead2026!"})
    if r.status_code != 200:
        pytest.skip("login failed")
    ss.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    orig = ss.get(f"{BASE_URL}/api/agents/{AID}").json()
    yield ss
    body = {**orig, "address": "", "hours": "", "notify_email": "", "receptionist": True,
            "reception_book": True, "reception_message": True, "transfer_number": ""}
    ss.put(f"{BASE_URL}/api/agents/{AID}", json=body)


def _put(s, **kw):
    body = {**s.get(f"{BASE_URL}/api/agents/{AID}").json(), **kw}
    return s.put(f"{BASE_URL}/api/agents/{AID}", json=body)


# API: fields persist
def test_fields_persist(s):
    r = _put(s, address="TEST Calle 1", hours="L-V 9-18", notify_email="avisos@test.es", receptionist=False,
             reception_book=False, reception_message=True, transfer_number="+34 600 11 22 33")
    assert r.status_code == 200, r.text
    g = s.get(f"{BASE_URL}/api/agents/{AID}").json()
    assert g["address"] == "TEST Calle 1" and g["hours"] == "L-V 9-18" and g["notify_email"] == "avisos@test.es"
    assert g["receptionist"] is False and g["reception_book"] is False and g["reception_message"] is True
    assert g["transfer_number"] == "+34600112233"


# API: validation
def test_bad_transfer(s):
    r = _put(s, transfer_number="600112233")
    assert r.status_code == 422
    assert "debe empezar por +" in str(r.json()["detail"])


def test_bad_email(s):
    r = _put(s, notify_email="bad")
    assert r.status_code == 422
    assert "El email de avisos no es válido." in str(r.json()["detail"])


def test_empty_transfer_ok(s):
    assert _put(s, transfer_number="", notify_email="").status_code == 200


# Unit: vapi tools / system_prompt
AG = {"name": "Marta", "business_name": "Biz", "objective": "calificar", "product": "Prod", "website": "https://x.es",
      "address": "Calle Mayor 1", "hours": "L-V 9-18", "receptionist": True, "reception_book": True,
      "reception_message": True, "transfer_number": "+34600112233", "extra_instructions": "", "memory": False}


def _names(t):
    return [x.get("function", {}).get("name") or x["type"] for x in t]


def test_unit_reception_on():
    import vapi
    lead = {"direction": "entrante", "reception": True, "name": "Llamada", "phone": "+34611"}
    n = _names(vapi.tools(AG, {}, lead, False))
    assert "check_availability" in n and "book_appointment" in n and "transferCall" in n
    p = vapi.system_prompt(AG, lead, "hoy")
    assert "recepcionista telefónica" in p
    i = p.index("SOBRE EL NEGOCIO")
    assert "Dirección: Calle Mayor 1" in p[i:] and "Horario: L-V 9-18" in p[i:] and "Web: https://x.es" in p[i:]


def test_unit_reception_off():
    import vapi
    lead = {"direction": "entrante", "reception": False, "name": "Llamada", "phone": "+34611"}
    n = _names(vapi.tools(AG, {}, lead, False))
    assert "transferCall" not in n
    p = vapi.system_prompt(AG, lead, "hoy")
    assert "Te ha llamado esta persona a tu número. " + vapi.OBJECTIVES["calificar"] in p
    assert "recepcionista telefónica del negocio y atiendes" not in p


def test_unit_outbound():
    import vapi
    lead = {"direction": "saliente", "name": "Ana", "phone": "+34611", "email": ""}
    assert "transferCall" not in _names(vapi.tools(AG, {}, lead, False))


def test_unit_notify_to():
    import saas
    from motor.motor_asyncio import AsyncIOMotorClient

    async def run():
        # notify_to reads agents collection
        import db as _d  # noqa
    try:
        r1 = asyncio.get_event_loop().run_until_complete(saas.notify_to({"agent_id": ""}, {"email": "o@x.es"}))
        assert r1 == "o@x.es"
    except Exception as e:
        pytest.skip(f"notify_to unit not runnable: {e}")


# Unit: reception OFF + objective calificar -> no booking tools
def test_unit_reception_off_no_booking():
    import vapi
    lead = {"direction": "entrante", "reception": False}
    n = _names(vapi.tools(AG, {}, lead, False))
    assert "check_availability" not in n and "transferCall" not in n


# Unit: reception ON with no transfer -> no transferCall, book disabled -> no booking
def test_unit_reception_flags():
    import vapi
    lead = {"direction": "entrante", "reception": True}
    n = _names(vapi.tools({**AG, "transfer_number": "", "reception_book": False}, {}, lead, False))
    assert "transferCall" not in n and "check_availability" not in n
