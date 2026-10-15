import json
import re
import time

import httpx
import pytest
from conftest import future, jpeg_bytes, loc, make_admin, make_carrier, make_user
from sqlalchemy import select

from app.config import settings
from app.db import uow
from app.models import AdminUser, CarrierProfile, User
from app.security import sign_init_data, validate_init_data, InvalidInitData

BOT_TOKEN = "123456:TEST-token"


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "bot_token", BOT_TOKEN)
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def tg_id(user_id: int) -> int:
    async with uow() as s:
        return (await s.get(User, user_id)).telegram_id


def dev(telegram_id: int) -> dict:
    return {"Authorization": f"dev {telegram_id}"}


def test_init_data_signature():
    fields = {"auth_date": str(int(time.time())), "user": json.dumps({"id": 42, "first_name": "A"}), "query_id": "x"}
    data = sign_init_data(fields, BOT_TOKEN)
    assert validate_init_data(data, BOT_TOKEN, 3600)["id"] == 42
    with pytest.raises(InvalidInitData):
        validate_init_data(data.replace("first_name", "first_namX"), BOT_TOKEN, 3600)
    with pytest.raises(InvalidInitData):
        validate_init_data(data, "999:other", 3600)
    old = sign_init_data({**fields, "auth_date": str(int(time.time()) - 7200)}, BOT_TOKEN)
    with pytest.raises(InvalidInitData):
        validate_init_data(old, BOT_TOKEN, 3600)


async def test_auth_required_and_tma_header(client):
    assert (await client.get("/api/me")).status_code == 401
    uid = await make_user()
    fields = {"auth_date": str(int(time.time())), "user": json.dumps({"id": await tg_id(uid), "first_name": "Ali"})}
    r = await client.get("/api/me", headers={"Authorization": "tma " + sign_init_data(fields, BOT_TOKEN)})
    assert r.status_code == 200 and r.json()["registered"] is True


async def test_unregistered_user_cannot_post(client):
    uid = await make_user(registered=False)
    r = await client.post("/api/listings", json={"kind": "REQUEST", "category": "PASSENGER"}, headers=dev(await tg_id(uid)))
    assert r.status_code == 403 and r.json()["error"] == "not_registered"


async def test_parcel_request_privacy_and_offer_flow(client):
    client_uid = await make_user("Mijoz")
    carrier_uid, vehicle_id = await make_carrier("Tashuvchi")
    stranger = await make_user("Begona")
    c_h, k_h, s_h = dev(await tg_id(client_uid)), dev(await tg_id(carrier_uid)), dev(await tg_id(stranger))

    photo = await client.post("/api/files", data={"purpose": "LISTING_PHOTO"},
                              files={"file": ("p.jpg", jpeg_bytes(), "image/jpeg")}, headers=c_h)
    assert photo.status_code == 200, photo.text
    bad = await client.post("/api/files", data={"purpose": "LISTING_PHOTO"},
                            files={"file": ("x.jpg", b"not an image", "image/jpeg")}, headers=c_h)
    assert bad.json()["error"] == "invalid_file"

    body = {
        "kind": "REQUEST", "category": "PARCEL",
        "from_location_id": await loc("Toshkent"), "to_location_id": await loc("Farg'ona"),
        "departure_at": future(30).isoformat(), "price": 60_000,
        "description": "Kitoblar qutisi", "quantity": 1, "weight_kg": 5,
        "length_cm": 40, "width_cm": 30, "height_cm": 20,
        "photo_ids": [photo.json()["id"]],
        "from_address": "Yunusobod 5-kvartal", "to_address": "Farg'ona, Mustaqillik 12",
        "recipient_name": "Olim", "recipient_phone": "+998 90 111 22 33",
    }
    r = await client.post("/api/listings", json={**body, "photo_ids": []}, headers=c_h)
    assert r.json()["error"] == "photos_required"
    r = await client.post("/api/listings", json=body, headers=c_h)
    assert r.status_code == 200, r.text
    listing = r.json()
    assert listing["from_address"] == "Yunusobod 5-kvartal"  # the author sees own addresses

    found = (await client.get("/api/listings", params={"kind": "REQUEST", "from_location_id": body["from_location_id"]}, headers=k_h)).json()
    seen = next(x for x in found if x["id"] == listing["id"])
    assert "from_address" not in seen and "recipient_phone" not in seen
    # photos of public listings are visible to registered users
    assert (await client.get(f"/api/files/{photo.json()['id']}", headers=k_h)).status_code == 200

    r = await client.post(f"/api/listings/{listing['id']}/offers", json={"price": 70_000, "vehicle_id": vehicle_id}, headers=k_h)
    assert r.status_code == 200, r.text
    offer = r.json()
    # a stranger can see neither the offers of the listing nor the order
    assert (await client.get(f"/api/listings/{listing['id']}/offers", headers=s_h)).json() == []

    r = await client.post(f"/api/offers/{offer['id']}/accept", headers=c_h)
    assert r.status_code == 200 and r.json()["status"] == "AWAITING_CONFIRMATION"
    order_id = r.json()["order_id"]

    view = (await client.get(f"/api/orders/{order_id}", headers=k_h)).json()
    assert view["revealed"] is False and "from_address" not in view and "phone" not in view["counterparty"]
    assert view["actions"] == ["confirm", "cancel"]
    assert (await client.get(f"/api/orders/{order_id}", headers=s_h)).status_code == 403

    view = (await client.post(f"/api/orders/{order_id}/confirm", headers=k_h)).json()
    assert view["revealed"] is True
    assert view["from_address"] == "Yunusobod 5-kvartal" and view["recipient_phone"] == "+998 90 111 22 33"
    assert view["counterparty"]["phone"] == "+998901234567"
    assert view["vehicle"]["plate_number"] == "01A123BC"

    assert (await client.post(f"/api/orders/{order_id}/complete", headers=c_h)).json()["error"] == "invalid_transition"
    await client.post(f"/api/orders/{order_id}/start", headers=k_h)
    # parcel handover: the client sees the code, the carrier must enter it
    code = (await client.get(f"/api/orders/{order_id}", headers=c_h)).json()["delivery_code"]
    assert code and len(code) == 4
    assert (await client.post(f"/api/orders/{order_id}/deliver", headers=k_h)).json()["error"] == "code_required"
    r = await client.post(f"/api/orders/{order_id}/deliver", json={"code": code}, headers=k_h)
    assert r.json()["status"] == "AWAITING_COMPLETION", r.text
    done = (await client.post(f"/api/orders/{order_id}/complete", headers=c_h)).json()
    assert done["status"] == "COMPLETED" and done["actions"] == ["review"]
    rev = (await client.post(f"/api/orders/{order_id}/review", json={"rating": 5, "text": "rahmat"}, headers=c_h)).json()
    assert rev["my_review"]["rating"] == 5 and rev["actions"] == []
    assert (await client.post(f"/api/orders/{order_id}/explode", headers=c_h)).status_code == 404


async def test_carrier_verification_via_api_and_admin(client, notifier):
    uid = await make_user("Yangi haydovchi")
    h = dev(await tg_id(uid))
    r = await client.post("/api/carrier/submit", json={"full_name": "Aliyev Vali"}, headers=h)
    assert r.json()["error"] == "documents_missing"
    v = await client.post("/api/carrier/vehicles", json={"vehicle_type": "SEDAN", "make_model": "Gentra",
                                                         "plate_number": "01 a 777 aa", "seats": 4}, headers=h)
    assert v.json()["plate_number"] == "01A777AA"
    for kind in ("DRIVER_LICENSE", "TECH_PASSPORT", "VEHICLE_PHOTO"):
        f = await client.post("/api/files", data={"purpose": "DOCUMENT"}, files={"file": ("d.jpg", jpeg_bytes(), "image/jpeg")}, headers=h)
        assert (await client.post("/api/carrier/documents", json={"kind": kind, "file_id": f.json()["id"]}, headers=h)).status_code == 200
    r = await client.post("/api/carrier/submit", json={"full_name": "Aliyev Vali"}, headers=h)
    assert r.json()["status"] == "PENDING"
    assert any(m.key == "admin.verification_submitted" for m in notifier.messages)

    # documents are private
    other = dev(await tg_id(await make_user()))
    doc_file = (await client.get("/api/carrier", headers=h)).json()["documents"][0]["file_id"]
    assert (await client.get(f"/api/files/{doc_file}", headers=other)).status_code == 404

    # admin panel login + approve
    admin_id = await make_admin("MODERATOR")
    async with uow() as s:
        admin_name = (await s.get(AdminUser, admin_id)).username
        profile_id = (await s.execute(select(CarrierProfile.id).where(CarrierProfile.user_id == uid))).scalar_one()

    page = await client.get("/admin/login")
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    bad = await client.post("/admin/login", data={"csrf": csrf, "username": admin_name, "password": "wrong"})
    assert bad.headers["location"] == "/admin/login"
    ok = await client.post("/admin/login", data={"csrf": csrf, "username": admin_name, "password": "secret123"})
    assert ok.headers["location"] == "/admin/"
    assert (await client.get("/admin/")).status_code == 200
    detail = await client.get(f"/admin/verifications/{profile_id}")
    assert "Aliyev Vali" in detail.text
    # moderators have no access to settings
    assert (await client.get("/admin/settings")).headers["location"] == "/admin/"
    # missing CSRF token is rejected
    await client.post(f"/admin/verifications/{profile_id}/approve", data={"categories": ["PASSENGER"]})
    assert (await client.get("/api/me", headers=h)).json()["carrier"]["status"] == "PENDING"

    csrf = re.search(r'name="csrf" value="([^"]+)"', detail.text).group(1)
    r = await client.post(f"/admin/verifications/{profile_id}/approve", data={"csrf": csrf, "categories": ["PASSENGER"]})
    assert r.status_code == 303
    me = (await client.get("/api/me", headers=h)).json()
    assert me["carrier"]["status"] == "APPROVED" and me["carrier"]["permissions"] == ["PASSENGER"]
    assert "carrier.approved" in notifier.keys(uid)

    for path in ("/admin/users", f"/admin/users/{uid}", "/admin/listings", "/admin/verifications", "/admin/reviews"):
        assert (await client.get(path)).status_code == 200, path


async def test_admin_pages_render_for_superadmin(client):
    admin_id = await make_admin("SUPERADMIN")
    async with uow() as s:
        name = (await s.get(AdminUser, admin_id)).username
    page = await client.get("/admin/login")
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    await client.post("/admin/login", data={"csrf": csrf, "username": name, "password": "secret123"})
    for path in ("/admin/", "/admin/orders", "/admin/complaints", "/admin/settings", "/admin/audit"):
        r = await client.get(path)
        assert r.status_code == 200, path
    settings_page = await client.get("/admin/settings")
    csrf = re.search(r'name="csrf" value="([^"]+)"', settings_page.text).group(1)
    await client.post("/admin/settings", data={"csrf": csrf, "commission_percent": "7.5", "enabled_categories": "PASSENGER,PARCEL,DOCUMENTS"})
    cfg = (await client.get("/api/config", headers=dev(await tg_id(await make_user())))).json()
    assert cfg["commission_percent"] == 7.5 and "DOCUMENTS" in cfg["enabled_categories"]
    assert "setting.update" in (await client.get("/admin/audit")).text


async def test_terms_and_health(client):
    assert (await client.get("/healthz")).json() == {"ok": True}
    assert "Условия" in (await client.get("/terms?lang=ru")).text
