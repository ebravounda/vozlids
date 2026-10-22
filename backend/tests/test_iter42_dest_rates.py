# Iteration 42: per-destination tariffs, Zadarma compare/weekly, CL number cost, margins regression
import os
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"email": "admin@vozlead.es", "password": "VozLead2026!"}


def _env(path, key):
    for line in open(path):
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip().strip('"')


@pytest.fixture(scope="module")
def mdb():
    c = MongoClient(_env("/app/backend/.env", "MONGO_URL"))
    return c[_env("/app/backend/.env", "DB_NAME")]


@pytest.fixture(scope="module")
def admin():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN)
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="module")
def client_user():
    s = requests.Session()
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{BASE_URL}/api/auth/register", json={"name": "T", "business_name": "TEST_biz", "email": email, "password": "Test12345!"})
    if r.status_code not in (200, 201):
        pytest.skip(f"register failed {r.status_code}")
    return s


# Dest rates API
class TestDestRates:
    def test_empty(self, admin, mdb):
        mdb.platform_settings.delete_one({"_id": "dest_rates"})
        r = admin.get(f"{BASE_URL}/api/admin/pricing/dest-rates")
        assert r.status_code == 200
        assert r.json() == {"rates": []}

    def test_put_unknown_404(self, admin):
        r = admin.put(f"{BASE_URL}/api/admin/pricing/dest-rates/XX", json={"usd_min": 0.1})
        assert r.status_code == 404

    def test_seed_edit_reset(self, admin, mdb):
        mdb.platform_settings.update_one({"_id": "dest_rates"}, {"$set": {"rates": {"GT": {"usd_min": 0.14, "name": "Guatemala", "manual": False}}}}, upsert=True)
        try:
            r = admin.get(f"{BASE_URL}/api/admin/pricing/dest-rates").json()["rates"]
            assert r[0]["code"] == "GT" and r[0]["usd_min"] == 0.14
            r = admin.put(f"{BASE_URL}/api/admin/pricing/dest-rates/gt", json={"usd_min": 0.2})
            assert r.status_code == 200
            gt = r.json()["rates"][0]
            assert gt["usd_min"] == 0.2 and gt["manual"] is True
            # invalid value
            assert admin.put(f"{BASE_URL}/api/admin/pricing/dest-rates/GT", json={"usd_min": -1}).status_code == 422
            assert admin.put(f"{BASE_URL}/api/admin/pricing/dest-rates/GT", json={"usd_min": 9}).status_code == 422
            # pricing includes dest_rates
            costs = admin.get(f"{BASE_URL}/api/admin/costs").json()
            assert costs["pricing"]["dest_rates"]["GT"]["usd_min"] == 0.2
            r = admin.delete(f"{BASE_URL}/api/admin/pricing/dest-rates/GT/manual")
            assert r.status_code == 200
            assert r.json()["rates"][0]["manual"] is False
        finally:
            mdb.platform_settings.delete_one({"_id": "dest_rates"})

    def test_reset_unknown_code(self, admin, mdb):
        # reset of unknown code on existing doc should not create junk entries
        mdb.platform_settings.update_one({"_id": "dest_rates"}, {"$set": {"rates": {"GT": {"usd_min": 0.14, "name": "Guatemala", "manual": False}}}}, upsert=True)
        try:
            r = admin.delete(f"{BASE_URL}/api/admin/pricing/dest-rates/ZZ/manual")
            codes = [x["code"] for x in r.json()["rates"]]
            assert "ZZ" not in codes, f"junk entry created: {r.json()}"
        finally:
            mdb.platform_settings.delete_one({"_id": "dest_rates"})

    def test_non_admin_403(self, client_user):
        assert client_user.get(f"{BASE_URL}/api/admin/pricing/dest-rates").status_code == 403


# Costs / pricing
class TestCosts:
    def test_costs(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/costs")
        assert r.status_code == 200
        p = r.json()["pricing"]
        assert p["number_cl_usd_month"] == 6
        assert "dest_rates" in p

    def test_margins(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/monitor/margins")
        assert r.status_code == 200
        assert isinstance(r.json(), (dict, list))


# Zadarma compare / weekly
class TestZadarma:
    def test_compare(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/costs/zadarma-compare", params={"days": 7})
        assert r.status_code == 200
        d = r.json()
        assert d["error"] and d["rows"] == []

    def test_weekly_admin(self, admin):
        r = admin.post(f"{BASE_URL}/api/admin/costs/zadarma-weekly")
        assert r.status_code == 200
        d = r.json()
        assert d["sent"] is False and "Zadarma" in d["error"]

    def test_weekly_non_admin(self, client_user):
        assert client_user.post(f"{BASE_URL}/api/admin/costs/zadarma-weekly").status_code == 403
        assert client_user.get(f"{BASE_URL}/api/admin/costs/zadarma-compare").status_code == 403
