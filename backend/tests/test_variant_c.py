"""Variant C contract: trust data, price hint, listing activity, whole_car, parcel delivery code."""

from datetime import timedelta

import pytest
from conftest import future, loc, make_carrier, make_user, passenger_request, passenger_route
from test_api import client, dev, tg_id  # noqa: F401  (client fixture)

from app.db import uow
from app.enums import OrderStatus
from app.models import Document, Listing, Order, StoredFile, Subscription, User
from app.services import listings, offers, orders, pricing, profiles, reviews
from app.services.errors import DomainError
from app.timeutil import now


async def _user(s, uid):
    return await s.get(User, uid)


async def parcel_request(client_id: int, price: int = 60_000) -> int:
    async with uow() as s:
        f = StoredFile(owner_id=client_id, path="x.jpg", mime="image/jpeg", size=1, purpose="LISTING_PHOTO")
        s.add(f)
        await s.flush()
        data = {
            "kind": "REQUEST", "category": "PARCEL",
            "from_location_id": await loc("Toshkent"), "to_location_id": await loc("Farg'ona"),
            "departure_at": future(30), "price": price,
            "description": "Quti", "quantity": 1, "weight_kg": 5, "length_cm": 40, "width_cm": 30, "height_cm": 20,
            "photo_ids": [f.id], "from_address": "Yunusobod", "to_address": "Mustaqillik 12",
            "recipient_name": "Olim", "recipient_phone": "+998901112233",
        }
        return (await listings.create(s, await _user(s, client_id), data)).id


async def in_progress_order(listing_id: int, client_id: int, carrier_id: int, vehicle_id: int) -> int:
    async with uow() as s:
        offer = await offers.create(s, await _user(s, carrier_id), listing_id, {"price": 70_000, "vehicle_id": vehicle_id})
    async with uow() as s:
        order = await offers.accept(s, await _user(s, client_id), offer.id)
    async with uow() as s:
        await orders.confirm(s, await _user(s, carrier_id), order.id)
    async with uow() as s:
        await orders.start(s, await _user(s, carrier_id), order.id)
    return order.id


async def complete_order(order_id: int, client_id: int, carrier_id: int, code: str | None = None):
    async with uow() as s:
        await orders.deliver(s, await _user(s, carrier_id), order_id, code)
    async with uow() as s:
        await orders.complete(s, await _user(s, client_id), order_id)


# ---------------------------------------------------------------- G: delivery code


async def test_delivery_code_flow(client, notifier):
    client_uid = await make_user("Mijoz")
    carrier_uid, vehicle = await make_carrier("Karim")
    order_id = await in_progress_order(await parcel_request(client_uid), client_uid, carrier_uid, vehicle)
    async with uow() as s:
        code = (await s.get(Order, order_id)).delivery_code
    assert code and len(code) == 4 and code.isdigit()
    msg = next(m for m in notifier.messages if m.key == "order.delivery_code")
    assert msg.user_id == client_uid and msg.params["code"] == code
    assert all(m.user_id != carrier_uid for m in notifier.messages if m.key == "order.delivery_code")

    c_h, k_h = dev(await tg_id(client_uid)), dev(await tg_id(carrier_uid))
    cv = (await client.get(f"/api/orders/{order_id}", headers=c_h)).json()
    kv = (await client.get(f"/api/orders/{order_id}", headers=k_h)).json()
    assert cv["delivery_code"] == code and cv["needs_code"] is False and cv["code_attempts_left"] is None
    assert kv["delivery_code"] is None and kv["needs_code"] is True and kv["code_attempts_left"] == 5
    assert [x["status"] for x in kv["timeline"]] == ["AWAITING_CONFIRMATION", "CONFIRMED", "IN_PROGRESS"]

    r = await client.post(f"/api/orders/{order_id}/deliver", headers=k_h)
    assert r.status_code == 400 and r.json()["error"] == "code_required"
    wrong = "0000" if code != "0000" else "1111"
    r = await client.post(f"/api/orders/{order_id}/deliver", json={"code": wrong}, headers=k_h)
    assert r.json() == {"error": "invalid_code", "params": {"attempts_left": 4}}
    kv = (await client.get(f"/api/orders/{order_id}", headers=k_h)).json()
    assert kv["code_attempts_left"] == 4 and kv["status"] == "IN_PROGRESS"
    # the client cannot deliver even with the code
    assert (await client.post(f"/api/orders/{order_id}/deliver", json={"code": code}, headers=c_h)).status_code == 403

    r = await client.post(f"/api/orders/{order_id}/deliver", json={"code": f" {code} "}, headers=k_h)
    assert r.status_code == 200 and r.json()["status"] == "AWAITING_COMPLETION"
    assert r.json()["code_attempts_left"] == 4
    # the client still sees the code until the order is completed
    assert (await client.get(f"/api/orders/{order_id}", headers=c_h)).json()["delivery_code"] == code
    done = (await client.post(f"/api/orders/{order_id}/complete", headers=c_h)).json()
    assert done["status"] == "COMPLETED" and done["delivery_code"] is None
    # other generic actions still work through /orders/{id}/{action}
    assert (await client.post(f"/api/orders/{order_id}/explode", headers=c_h)).status_code == 404


async def test_locked_code_hides_deliver_and_bot_requires_code(client):
    from test_bot import cb_update, feed, make_bot
    from aiogram.methods import AnswerCallbackQuery

    client_uid = await make_user()
    carrier_uid, vehicle = await make_carrier()
    order_id = await in_progress_order(await parcel_request(client_uid), client_uid, carrier_uid, vehicle)
    k_h = dev(await tg_id(carrier_uid))

    # Telegram quick action cannot deliver a parcel without the code
    bot, dp, session = make_bot()
    await feed(bot, dp, cb_update(await tg_id(carrier_uid), f"o:deliver:{order_id}"))
    answer = [c for c in session.calls if isinstance(c, AnswerCallbackQuery)][-1]
    assert answer.show_alert
    async with uow() as s:
        assert (await s.get(Order, order_id)).status == OrderStatus.IN_PROGRESS

    view = (await client.get(f"/api/orders/{order_id}", headers=k_h)).json()
    assert view["actions"] == ["deliver", "complain"] and view["code_locked"] is False
    async with uow() as s:
        (await s.get(Order, order_id)).delivery_code_attempts = orders.DELIVERY_CODE_MAX_ATTEMPTS
    view = (await client.get(f"/api/orders/{order_id}", headers=k_h)).json()
    assert view["actions"] == ["complain"] and view["code_locked"] is True


async def test_delivery_code_locks_after_five_wrong_attempts():
    client_uid = await make_user()
    carrier_uid, vehicle = await make_carrier()
    order_id = await in_progress_order(await parcel_request(client_uid), client_uid, carrier_uid, vehicle)
    async with uow() as s:
        code = (await s.get(Order, order_id)).delivery_code
    wrong = "0000" if code != "0000" else "1111"
    left = []
    for _ in range(5):
        with pytest.raises(DomainError) as e:
            async with uow() as s:  # a real unit of work: the failed attempt must survive the error
                await orders.deliver(s, await _user(s, carrier_uid), order_id, wrong)
        left.append((e.value.code, e.value.params.get("attempts_left")))
    assert left == [("invalid_code", 4), ("invalid_code", 3), ("invalid_code", 2), ("invalid_code", 1), ("code_locked", None)]
    with pytest.raises(DomainError) as e:
        async with uow() as s:  # even the correct code is refused now; resolved through a complaint
            await orders.deliver(s, await _user(s, carrier_uid), order_id, code)
    assert e.value.code == "code_locked"
    async with uow() as s:
        o = await s.get(Order, order_id)
        assert o.status == OrderStatus.IN_PROGRESS and o.delivery_code_attempts == 5
        assert orders.code_attempts_left(o) == 0
    async with uow() as s:
        await orders.complain(s, await _user(s, client_uid), order_id, "NO_SHOW", None)


async def test_passenger_order_needs_no_code(notifier):
    client_uid = await make_user()
    carrier_uid, vehicle = await make_carrier()
    order_id = await in_progress_order(await passenger_request(client_uid), client_uid, carrier_uid, vehicle)
    async with uow() as s:
        o = await s.get(Order, order_id)
        assert o.delivery_code is None and not orders.needs_delivery_code(o)
        assert orders.code_attempts_left(o) is None
    assert not any(m.key == "order.delivery_code" for m in notifier.messages)
    async with uow() as s:
        o = await orders.deliver(s, await _user(s, carrier_uid), order_id)
        assert o.status == OrderStatus.AWAITING_COMPLETION


# ---------------------------------------------------------------- A/B: trust data


async def test_trips_and_verified_in_offers_and_profile(client):
    client_uid = await make_user("Mijoz")
    carrier_uid, vehicle = await make_carrier("Karim")
    newbie = await make_user("Yangi")
    for _ in range(2):
        order_id = await in_progress_order(await passenger_request(client_uid), client_uid, carrier_uid, vehicle)
        await complete_order(order_id, client_uid, carrier_uid)
    async with uow() as s:
        await reviews.create(s, await _user(s, client_uid), order_id, 5, "zo'r")
        s.add(Document(user_id=carrier_uid, kind="DRIVER_LICENSE", file_id=(await _file(s, carrier_uid))))
        s.add(Document(user_id=carrier_uid, kind="VEHICLE_PHOTO", file_id=(await _file(s, carrier_uid))))

    async with uow() as s:
        stats = await profiles.public_stats(s, [carrier_uid, client_uid, newbie])
    assert stats[carrier_uid] == {"trips": 2, "verified": True}
    assert stats[client_uid] == {"trips": 2, "verified": False}
    assert stats[newbie] == {"trips": 0, "verified": False}

    listing_id = await passenger_request(client_uid)
    k_h, c_h = dev(await tg_id(carrier_uid)), dev(await tg_id(client_uid))
    await client.post(f"/api/listings/{listing_id}/offers", json={"price": 150_000, "vehicle_id": vehicle}, headers=k_h)
    offers_view = (await client.get(f"/api/listings/{listing_id}/offers", headers=c_h)).json()
    assert offers_view[0]["counterparty"]["trips"] == 2 and offers_view[0]["counterparty"]["verified"] is True
    found = (await client.get("/api/listings", params={"kind": "REQUEST"}, headers=k_h)).json()
    author = next(x for x in found if x["id"] == listing_id)["author"]
    assert author["trips"] == 2 and author["verified"] is False

    p = (await client.get(f"/api/users/{carrier_uid}", headers=c_h)).json()
    assert p["id"] == carrier_uid and p["name"] == "Karim" and p["trips"] == 2 and p["verified"] is True
    assert p["rating"] == 5 and p["rating_count"] == 1 and p["member_since"]
    assert p["checks"] == {"phone": True, "driver_license": True, "tech_passport": False, "vehicle_photo": True}
    assert p["reviews"] == [{"rating": 5, "text": "zo'r", "author": "Mijoz", "created_at": p["reviews"][0]["created_at"]}]
    # documents count only for an approved profile
    q = (await client.get(f"/api/users/{newbie}", headers=c_h)).json()
    assert q["verified"] is False and q["checks"]["driver_license"] is False and q["checks"]["phone"] is True
    assert (await client.get("/api/users/99999", headers=c_h)).status_code == 404


async def _file(s, owner_id: int) -> int:
    f = StoredFile(owner_id=owner_id, path="d.jpg", mime="image/jpeg", size=1, purpose="DOCUMENT")
    s.add(f)
    await s.flush()
    return f.id


# ---------------------------------------------------------------- C: price hint


async def test_price_hint_by_distance(client):
    uid = await make_user()
    h = dev(await tg_id(uid))
    tash, sam = await loc("Toshkent"), await loc("Samarqand")
    r = (await client.get("/api/price-hint", params={"category": "PASSENGER", "from_location_id": tash,
                                                     "to_location_id": sam}, headers=h)).json()
    assert r["source"] == "distance" and 330 <= r["distance_km"] <= 400
    assert r["min"] < r["typical"] < r["max"] and all(r[k] % 5_000 == 0 for k in ("min", "max", "typical"))
    async with uow() as s:
        a, b = await s.get(pricing.Location, tash), await s.get(pricing.Location, sam)
        km = pricing.haversine_km(a.lat, a.lon, b.lat, b.lon) * 1.25
    assert r["typical"] == pricing.round_price(km * 550)
    two = (await client.get("/api/price-hint", params={"category": "PASSENGER", "from_location_id": tash,
                                                       "to_location_id": sam, "seats": 2}, headers=h)).json()
    assert two["typical"] == pricing.round_price(km * 550 * 2)
    parcel = (await client.get("/api/price-hint", params={"category": "PARCEL", "from_location_id": tash,
                                                          "to_location_id": sam, "seats": 3}, headers=h)).json()
    assert parcel["typical"] == pricing.round_price(km * 250)  # seats do not multiply parcels
    bad = await client.get("/api/price-hint", params={"category": "PASSENGER", "from_location_id": tash,
                                                      "to_location_id": tash}, headers=h)
    assert bad.json()["error"] == "same_locations"


async def test_price_hint_from_history():
    client_uid = await make_user()
    carrier_uid, vehicle = await make_carrier(seats=4)
    # 2 passengers for 300k = 150k per seat; routes are priced per seat already
    await passenger_request(client_uid, price=300_000, passengers=2)
    for p in (100_000, 120_000, 140_000, 160_000):
        await passenger_route(carrier_uid, vehicle, price=p)
    async with uow() as s:
        tash, sam = await loc("Toshkent"), await loc("Samarqand")
        # old listings (> 90 days) are ignored
        old = await s.get(Listing, await passenger_route(carrier_uid, vehicle, price=900_000))
        old.created_at = now() - timedelta(days=91)
    async with uow() as s:
        r = await pricing.hint(s, "PASSENGER", tash, sam, 1)
        assert r["source"] == "history"
        # unit prices 100,120,140,150,160k -> p25=120k, p50=140k, p75=150k
        assert (r["min"], r["typical"], r["max"]) == (120_000, 140_000, 150_000)
        r2 = await pricing.hint(s, "PASSENGER", tash, sam, 2)
        assert (r2["min"], r2["typical"], r2["max"]) == (240_000, 280_000, 300_000)
        assert (await pricing.hint(s, "PARCEL", tash, sam, 1))["source"] == "distance"


# ---------------------------------------------------------------- D: activity, E: whole_car


async def test_listing_activity_author_only_and_unique_views(client):
    author = await make_user("Muallif")
    viewer = await make_user("Ko'ruvchi")
    carrier_sub, _ = await make_carrier("Obunachi")
    carrier_route, vehicle = await make_carrier("Marshrutchi")
    await make_carrier("Boshqa")  # approved, but neither subscribed nor driving this route
    no_perm, v2 = await make_carrier("ParcelOnly", categories=("PARCEL",))
    listing_id = await passenger_request(author, whole_car=True)
    await passenger_route(carrier_route, vehicle)
    async with uow() as s:
        s.add(Subscription(user_id=carrier_sub, kind="REQUEST", category="PASSENGER",
                           from_location_id=await loc("Toshkent"), to_location_id=await loc("Samarqand")))
        s.add(Subscription(user_id=no_perm, kind="REQUEST", category="PASSENGER",
                           from_location_id=await loc("Toshkent"), to_location_id=await loc("Samarqand")))

    a_h, v_h, k_h = dev(await tg_id(author)), dev(await tg_id(viewer)), dev(await tg_id(carrier_sub))
    url = f"/api/listings/{listing_id}"
    assert (await client.get(url + "/activity", headers=a_h)).json() == {"carriers_on_route": 2, "viewed": 0}
    assert (await client.get(url, headers=a_h)).json()["details"]["whole_car"] is True  # author views do not count
    for h in (v_h, v_h, k_h):
        assert (await client.get(url, headers=h)).status_code == 200
    assert (await client.get(url + "/activity", headers=a_h)).json() == {"carriers_on_route": 2, "viewed": 2}
    r = await client.get(url + "/activity", headers=v_h)
    assert r.status_code == 403 and r.json()["error"] == "forbidden"
    assert (await client.get("/api/listings/99999/activity", headers=a_h)).status_code == 404


async def test_whole_car_on_route_booking():
    client_uid = await make_user()
    carrier_uid, vehicle = await make_carrier(seats=4)
    route_id = await passenger_route(carrier_uid, vehicle, seats=4)
    async with uow() as s:
        o = await offers.create(s, await _user(s, client_uid), route_id, {
            "price": 400_000, "passengers": 4, "luggage": "2 chamadon", "whole_car": True,
            "from_address": "Chilonzor", "to_address": "Registon",
        })
        assert o.details["whole_car"] is True
    no_flag = await passenger_request(client_uid)
    async with uow() as s:
        assert (await s.get(Listing, no_flag)).details["whole_car"] is False


async def test_admin_order_page_shows_delivery_code(client):
    import re

    from conftest import make_admin

    from app.models import AdminUser

    client_uid = await make_user()
    carrier_uid, vehicle = await make_carrier()
    order_id = await in_progress_order(await parcel_request(client_uid), client_uid, carrier_uid, vehicle)
    async with uow() as s:
        code = (await s.get(Order, order_id)).delivery_code
        name = (await s.get(AdminUser, await make_admin("SUPPORT"))).username
    page = await client.get("/admin/login")
    csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
    await client.post("/admin/login", data={"csrf": csrf, "username": name, "password": "secret123"})
    html = (await client.get(f"/admin/orders/{order_id}")).text
    assert "Topshirish kodi" in html and f"<b>{code}</b>" in html and "0 / 5" in html
