# Iter37: KYC (identity documents) for client lines: client flow, admin review, provisioning gate
import os
import sys
import io
import uuid
import asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from pymongo import MongoClient
from dotenv import dotenv_values

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ENV = dotenv_values("/app/backend/.env")
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}
mdb = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00"
       b"\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82")


def _session(token):
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token}"
    return s


def _login(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds)
    assert r.status_code == 200, r.text
    return _session(r.json()["access_token"])


def _register(country="ES"):
    email = f"test_kyc_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE}/api/auth/register", json={"name": "TEST Kyc", "business_name": f"TEST_KYC {country}",
                                                        "email": email, "password": "TestPass123!", "country": country})
    assert r.status_code in (200, 201), r.text
    uid = r.json()["id"]
    return uid, _login({"email": email, "password": "TestPass123!"})


DATA = {"kind": "persona", "first_name": "Ana", "last_name": "García", "nationality": "ES", "id_type": "DNI",
        "id_number": "12345678Z", "email": "ana@example.com", "phone": "+34611222333", "city": "Madrid",
        "zip_code": "28001", "street": "Calle Mayor", "building_number": "5", "organization": "", "organization_reg_number": ""}


def up(s, t, content=PNG, mime="image/png", name="a.png"):
    return s.post(f"{BASE}/api/kyc/files", params={"type": t}, files={"file": (name, content, mime)})


@pytest.fixture(scope="module")
def ctx():
    admin = _login(ADMIN)
    uid, cli = _register("ES")
    mdb.users.update_one({"_id": ObjectId(uid)}, {"$set": {"billing_status": "active"}})
    uid_cl, cli_cl = _register("CL")
    mdb.tenant_numbers.insert_one({"tenant_id": uid_cl, "status": "activo", "country": "CL", "number": "+56900000000",
                                   "created_at": datetime.now(timezone.utc).isoformat()})
    uid_free, cli_free = _register("ES")
    c = {"admin": admin, "uid": uid, "cli": cli, "uid_cl": uid_cl, "cli_cl": cli_cl, "uid_free": uid_free, "cli_free": cli_free}
    yield c
    for u in (uid, uid_cl, uid_free):
        admin.delete(f"{BASE}/api/admin/users/{u}")
        mdb.tenant_numbers.delete_many({"tenant_id": u})
        mdb.kyc.delete_many({"tenant_id": u})


class TestKyc:
    def test_get_creates_es(self, ctx):
        r = ctx["cli"].get(f"{BASE}/api/kyc")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "sin_enviar" and d["required"] is True
        assert d["country"] == "ES" and "Ley 11/2022" in d["notice"]
        assert d["id_types"] == ["DNI", "NIE", "PASSPORT"]
        assert d["deadline"] == ""  # no active line
        assert mdb.kyc.find_one({"tenant_id": ctx["uid"]}) is not None

    def test_get_cl_with_line_deadline(self, ctx):
        d = ctx["cli_cl"].get(f"{BASE}/api/kyc").json()
        assert d["required"] is True and d["country"] == "CL"
        assert "18.168" in d["notice"] and d["id_types"] == ["NATIONAL_ID_CARD", "PASSPORT"]
        dl = datetime.fromisoformat(d["deadline"])
        assert abs((dl - datetime.now(timezone.utc)) - timedelta(days=30)) < timedelta(minutes=5)

    def test_not_required_free(self, ctx):
        d = ctx["cli_free"].get(f"{BASE}/api/kyc").json()
        assert d["required"] is False
        assert mdb.kyc.find_one({"tenant_id": ctx["uid_free"]}) is None

    def test_admin_not_required(self, ctx):
        assert ctx["admin"].get(f"{BASE}/api/kyc").json()["required"] is False

    def test_put_validation(self, ctx):
        r = ctx["cli"].put(f"{BASE}/api/kyc", json={**DATA, "kind": "empresa"})
        assert r.status_code == 422
        r = ctx["cli"].put(f"{BASE}/api/kyc", json={**DATA, "nationality": "esp"})
        assert r.status_code == 422

    def test_submit_without_data_or_files(self, ctx):
        r = ctx["cli"].post(f"{BASE}/api/kyc/submit")
        assert r.status_code == 422
        r = ctx["cli"].put(f"{BASE}/api/kyc", json=DATA)
        assert r.status_code == 200, r.text
        assert r.json()["first_name"] == "Ana"
        r = ctx["cli"].post(f"{BASE}/api/kyc/submit")
        assert r.status_code == 422
        msg = r.json()["detail"]
        assert "cara delantera" in msg and "cara trasera" in msg

    def test_upload_bad_type_and_mime(self, ctx):
        assert up(ctx["cli"], "selfie").status_code == 422
        assert up(ctx["cli"], "id_front", b"hello", "text/plain", "a.txt").status_code == 422

    def test_upload_too_big(self, ctx):
        r = up(ctx["cli"], "id_front", b"0" * (8 * 1024 * 1024 + 10), "image/jpeg", "big.jpg")
        assert r.status_code == 413

    def test_upload_and_replace(self, ctx):
        r = up(ctx["cli"], "id_front", name="front1.png")
        assert r.status_code == 200, r.text
        r = up(ctx["cli"], "id_front", name="front2.png")
        files = r.json()["files"]
        assert [f["name"] for f in files if f["type"] == "id_front"] == ["front2.png"]
        idx = files[0]["index"]
        g = ctx["cli"].get(f"{BASE}/api/kyc/files/{idx}")
        assert g.status_code == 200 and g.content == PNG and g.headers["content-type"].startswith("image/png")
        assert ctx["cli"].get(f"{BASE}/api/kyc/files/9").status_code == 404
        # other tenant cannot see it (own empty list)
        assert ctx["cli_free"].get(f"{BASE}/api/kyc/files/{idx}").status_code == 404

    def test_submit_missing_back_then_ok(self, ctx):
        r = ctx["cli"].post(f"{BASE}/api/kyc/submit")
        assert r.status_code == 422 and "trasera" in r.json()["detail"] and "delantera" not in r.json()["detail"]
        assert up(ctx["cli"], "id_back", b"%PDF-1.4 test", "application/pdf", "back.pdf").status_code == 200
        r = ctx["cli"].post(f"{BASE}/api/kyc/submit")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pendiente"

    def test_locked_after_submit(self, ctx):
        assert ctx["cli"].put(f"{BASE}/api/kyc", json=DATA).status_code == 409
        assert up(ctx["cli"], "id_front").status_code == 409
        assert ctx["cli"].post(f"{BASE}/api/kyc/submit").status_code == 409

    def test_admin_list_and_file(self, ctx):
        r = ctx["admin"].get(f"{BASE}/api/admin/kyc")
        assert r.status_code == 200
        rows = {x["tenant_id"]: x for x in r.json()}
        row = rows[ctx["uid"]]
        assert row["status"] == "pendiente" and row["business"] == "TEST_KYC ES" and row["overdue"] is False
        assert all("path" not in f for f in row["files"])
        assert ctx["uid_cl"] in rows
        g = ctx["admin"].get(f"{BASE}/api/admin/kyc/{ctx['uid']}/files/0")
        assert g.status_code == 200 and len(g.content) > 0

    def test_admin_endpoints_forbidden_for_client(self, ctx):
        assert ctx["cli"].get(f"{BASE}/api/admin/kyc").status_code == 403
        assert ctx["cli"].get(f"{BASE}/api/admin/kyc/{ctx['uid']}/files/0").status_code == 403
        assert ctx["cli"].post(f"{BASE}/api/admin/kyc/{ctx['uid']}/approve").status_code == 403
        assert ctx["cli"].post(f"{BASE}/api/admin/kyc/{ctx['uid']}/reject", json={"reason": "xxxx"}).status_code == 403

    def test_overdue_flag(self, ctx):
        mdb.kyc.update_one({"tenant_id": ctx["uid_cl"]}, {"$set": {"deadline": "2020-01-01T00:00:00+00:00"}})
        rows = {x["tenant_id"]: x for x in ctx["admin"].get(f"{BASE}/api/admin/kyc").json()}
        assert rows[ctx["uid_cl"]]["overdue"] is True

    def test_approve_without_zadarma_502(self, ctx):
        r = ctx["admin"].post(f"{BASE}/api/admin/kyc/{ctx['uid']}/approve")
        assert r.status_code == 424, r.text
        print("approve body (ingress may replace 502 body):", r.text[:120])
        assert mdb.kyc.find_one({"tenant_id": ctx["uid"]})["zadarma_status"]
        assert mdb.kyc.find_one({"tenant_id": ctx["uid"]})["status"] == "error"
        assert ctx["admin"].post(f"{BASE}/api/admin/kyc/{ctx['uid']}/check").status_code in (409, 502)

    def test_reject_and_resubmit(self, ctx):
        r = ctx["admin"].post(f"{BASE}/api/admin/kyc/{ctx['uid']}/reject", json={"reason": "x"})
        assert r.status_code == 422
        r = ctx["admin"].post(f"{BASE}/api/admin/kyc/{ctx['uid']}/reject", json={"reason": "Foto borrosa"})
        assert r.status_code == 200
        d = ctx["cli"].get(f"{BASE}/api/kyc").json()
        assert d["status"] == "rechazado" and d["reject_reason"] == "Foto borrosa"
        assert ctx["cli"].put(f"{BASE}/api/kyc", json={**DATA, "kind": "empresa", "organization": "TEST SL",
                                                        "organization_reg_number": "B12345678"}).status_code == 200
        r = ctx["cli"].post(f"{BASE}/api/kyc/submit")
        assert r.status_code == 422 and "certificado" in r.json()["detail"]
        assert up(ctx["cli"], "company_cert").status_code == 200
        r = ctx["cli"].post(f"{BASE}/api/kyc/submit")
        assert r.status_code == 200 and r.json()["status"] == "pendiente" and r.json()["reject_reason"] == ""

    def test_passport_requirement(self, ctx):
        s = ctx["cli_cl"]
        assert s.put(f"{BASE}/api/kyc", json={**DATA, "id_type": "PASSPORT", "nationality": "CL"}).status_code == 200
        r = s.post(f"{BASE}/api/kyc/submit")
        assert r.status_code == 422 and "pasaporte" in r.json()["detail"] and "delantera" not in r.json()["detail"]
        assert s.get(f"{BASE}/api/kyc").json()["required_files"] == ["passport"]

    def test_admin_404(self, ctx):
        assert ctx["admin"].post(f"{BASE}/api/admin/kyc/{'0' * 24}/reject", json={"reason": "abcd"}).status_code == 404


class TestProvisionGate:
    def test_gate_sets_pendiente_documentos(self, ctx):
        sys.path.insert(0, "/app/backend")
        os.chdir("/app/backend")
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        import phone_numbers as N
        uid = ctx["uid_free"]
        out = asyncio.new_event_loop().run_until_complete(N.provision(uid))
        assert out["status"] == "pendiente_documentos", out
        r = mdb.tenant_numbers.find_one({"tenant_id": uid})
        assert r["status"] == "pendiente_documentos" and not r.get("number")
        mdb.tenant_numbers.delete_many({"tenant_id": uid})


class TestRegression:
    def test_leads_language_filter(self, ctx):
        for lang in ("es", "en"):
            r = ctx["admin"].get(f"{BASE}/api/leads", params={"language": lang})
            assert r.status_code == 200, r.text
