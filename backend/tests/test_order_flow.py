from datetime import timedelta

import pytest
from conftest import future, loc, make_admin, make_carrier, make_user, passenger_request, passenger_route
from sqlalchemy import select

from app.db import uow
from app.enums import ListingStatus, OfferStatus, OrderStatus
from app.models import AdminUser, Cancellation, Listing, Offer, Order, OrderStatusHistory, User
from app.services import jobs, listings, offers, orders, reviews
from app.services.errors import DomainError
from app.timeutil import now


async def _user(s, uid):
    return await s.get(User, uid)


async def test_request_negotiation_full_cycle(notifier):
    client = await make_user("Mijoz")
    carrier, vehicle = await make_carrier("Karim")
    other_carrier, other_vehicle = await make_carrier("Botir")
    listing_id = await passenger_request(client, price=150_000)

    async with uow() as s:
        offer = await offers.create(s, await _user(s, carrier), listing_id, {"price": 180_000, "vehicle_id": vehicle})
        other = await offers.create(s, await _user(s, other_carrier), listing_id, {"price": 200_000, "vehicle_id": other_vehicle})
    assert "offer.new" in notifier.keys(client)

    async with uow() as s:  # client counters 160k
        counter = await offers.counter(s, await _user(s, client), offer.id, 160_000, "kelishamiz")

    async with uow() as s:  # proposer may not accept own proposal
        with pytest.raises(DomainError) as e:
            await offers.accept(s, await _user(s, client), counter.id)
        assert e.value.code == "not_your_turn"

    async with uow() as s:  # carrier accepts client's counter -> confirmed immediately
        order = await offers.accept(s, await _user(s, carrier), counter.id)
    assert order.status == OrderStatus.CONFIRMED
    assert order.price == 160_000
    assert order.estimated_commission == 16_000

    async with uow() as s:
        listing = await s.get(Listing, listing_id)
        assert listing.status == ListingStatus.CLOSED
        assert (await s.get(Offer, other.id)).status == OfferStatus.AUTO_CLOSED
        assert (await s.get(Offer, offer.id)).status == OfferStatus.COUNTERED
    assert "order.confirmed" in notifier.keys(client)
    assert "offer.closed" in notifier.keys(other_carrier)

    async with uow() as s:
        with pytest.raises(DomainError):  # the client cannot start the trip
            await orders.start(s, await _user(s, client), order.id)
    async with uow() as s:
        with pytest.raises(DomainError) as e:  # cannot complete before delivery
            await orders.complete(s, await _user(s, client), order.id)
        assert e.value.code == "invalid_transition"

    async with uow() as s:
        await orders.start(s, await _user(s, carrier), order.id)
    async with uow() as s:
        await orders.deliver(s, await _user(s, carrier), order.id)
    async with uow() as s:
        o = await orders.complete(s, await _user(s, client), order.id)
        assert o.status == OrderStatus.COMPLETED

    async with uow() as s:
        await reviews.create(s, await _user(s, client), order.id, 5, "zo'r")
        await reviews.create(s, await _user(s, carrier), order.id, 4, None)
    async with uow() as s:
        with pytest.raises(DomainError) as e:
            await reviews.create(s, await _user(s, client), order.id, 3, None)
        assert e.value.code == "already_reviewed"
    async with uow() as s:
        assert (await _user(s, carrier)).rating == 5
        assert (await _user(s, client)).rating == 4
        statuses = [h.to_status for h in await orders.history(s, order.id)]
        assert statuses == ["AWAITING_CONFIRMATION", "CONFIRMED", "IN_PROGRESS", "AWAITING_COMPLETION", "COMPLETED"]


async def test_client_accept_needs_carrier_confirmation_and_blocks_second_accept(notifier):
    client = await make_user()
    c1, v1 = await make_carrier()
    c2, v2 = await make_carrier()
    listing_id = await passenger_request(client)
    async with uow() as s:
        o1 = await offers.create(s, await _user(s, c1), listing_id, {"price": 150_000, "vehicle_id": v1})
        o2 = await offers.create(s, await _user(s, c2), listing_id, {"price": 140_000, "vehicle_id": v2})
    async with uow() as s:
        order = await offers.accept(s, await _user(s, client), o1.id)
    assert order.status == OrderStatus.AWAITING_CONFIRMATION
    assert "order.awaiting_confirmation" in notifier.keys(c1)

    async with uow() as s:
        with pytest.raises(DomainError) as e:
            await offers.accept(s, await _user(s, client), o2.id)
        assert e.value.code == "no_capacity"

    async with uow() as s:
        with pytest.raises(DomainError):  # only the carrier confirms
            await orders.confirm(s, await _user(s, client), order.id)
    async with uow() as s:
        await orders.confirm(s, await _user(s, c1), order.id)
    async with uow() as s:
        assert (await s.get(Order, order.id)).status == OrderStatus.CONFIRMED
        assert (await s.get(Offer, o2.id)).status == OfferStatus.AUTO_CLOSED


async def test_route_capacity_is_never_overbooked():
    carrier, vehicle = await make_carrier(seats=4)
    a, b = await make_user("A"), await make_user("B")
    listing_id = await passenger_route(carrier, vehicle, seats=2)
    booking = {"price": 240_000, "passengers": 2, "luggage": "yo'q", "from_address": "x", "to_address": "y"}
    async with uow() as s:
        oa = await offers.create(s, await _user(s, a), listing_id, booking)
        ob = await offers.create(s, await _user(s, b), listing_id, {**booking, "passengers": 1, "price": 120_000})
    async with uow() as s:
        with pytest.raises(DomainError) as e:  # 3 seats requested on a 2-seat route
            await offers.create(s, await _user(s, await make_user("C")), listing_id, {**booking, "passengers": 3})
        assert e.value.code == "no_capacity"

    async with uow() as s:  # carrier accepts A (client proposal) -> confirmed at once
        order = await offers.accept(s, await _user(s, carrier), oa.id)
        assert order.status == OrderStatus.CONFIRMED
    async with uow() as s:
        listing = await s.get(Listing, listing_id)
        assert listing.capacity_reserved == 2
        assert (await s.get(Offer, ob.id)).status == OfferStatus.AUTO_CLOSED
        found = await listings.search(s, {"kind": "ROUTE"})
        assert listing_id not in [x.id for x in found]


async def test_cancel_releases_capacity_and_reopens_request(notifier):
    client = await make_user()
    carrier, vehicle = await make_carrier()
    listing_id = await passenger_request(client)
    async with uow() as s:
        offer = await offers.create(s, await _user(s, carrier), listing_id, {"price": 150_000, "vehicle_id": vehicle})
    async with uow() as s:
        order = await offers.accept(s, await _user(s, client), offer.id)
    async with uow() as s:
        await orders.confirm(s, await _user(s, carrier), order.id)
    async with uow() as s:
        with pytest.raises(DomainError):
            await orders.cancel(s, await _user(s, carrier), order.id, "NOT_A_REASON", None)
    async with uow() as s:
        await orders.cancel(s, await _user(s, carrier), order.id, "VEHICLE_ISSUE", "mashina buzildi")
    async with uow() as s:
        listing = await s.get(Listing, listing_id)
        assert listing.status == ListingStatus.PUBLISHED
        assert listing.capacity_reserved == 0
        canc = (await s.execute(select(Cancellation))).scalar_one()
        assert canc.initiator_role == "CARRIER" and canc.status_at_cancel == "CONFIRMED"
        assert (await _user(s, carrier)).cancel_count == 1
    assert "order.cancelled" in notifier.keys(client)


async def test_confirmation_timeout_job_cancels_and_releases():
    client = await make_user()
    carrier, vehicle = await make_carrier()
    listing_id = await passenger_request(client)
    async with uow() as s:
        offer = await offers.create(s, await _user(s, carrier), listing_id, {"price": 150_000, "vehicle_id": vehicle})
    async with uow() as s:
        order = await offers.accept(s, await _user(s, client), offer.id)
    async with uow() as s:
        (await s.get(Order, order.id)).confirm_deadline = now() - timedelta(minutes=1)
    res = await jobs.run_once()
    assert res["timeout_confirmations"] == 1
    async with uow() as s:
        assert (await s.get(Order, order.id)).status == OrderStatus.CANCELLED
        assert (await s.get(Listing, listing_id)).capacity_reserved == 0


async def test_auto_complete_and_expirations():
    client = await make_user()
    carrier, vehicle = await make_carrier()
    listing_id = await passenger_request(client)
    stale_id = await passenger_request(client)
    async with uow() as s:
        offer = await offers.create(s, await _user(s, carrier), listing_id, {"price": 150_000, "vehicle_id": vehicle})
        pending = await offers.create(s, await _user(s, carrier), stale_id, {"price": 150_000, "vehicle_id": vehicle})
    async with uow() as s:
        order = await offers.accept(s, await _user(s, client), offer.id)
    async with uow() as s:
        await orders.confirm(s, await _user(s, carrier), order.id)
    async with uow() as s:
        await orders.start(s, await _user(s, carrier), order.id)
    async with uow() as s:
        await orders.deliver(s, await _user(s, carrier), order.id)
    async with uow() as s:
        (await s.get(Order, order.id)).auto_complete_at = now() - timedelta(seconds=1)
        (await s.get(Listing, stale_id)).departure_at = now() - timedelta(minutes=1)
        (await s.get(Offer, pending.id)).expires_at = now() - timedelta(minutes=1)
    res = await jobs.run_once()
    assert res["auto_complete"] == 1 and res["expire_offers"] == 1 and res["expire_listings"] == 1
    async with uow() as s:
        assert (await s.get(Order, order.id)).status == OrderStatus.COMPLETED
        assert (await s.get(Listing, stale_id)).status == ListingStatus.EXPIRED
        history = await orders.history(s, order.id)
        assert history[-1].actor_type == "SYSTEM"


async def test_dispute_blocks_completion_until_admin_decides(notifier):
    client = await make_user()
    carrier, vehicle = await make_carrier()
    admin_id = await make_admin()
    listing_id = await passenger_request(client)
    async with uow() as s:
        offer = await offers.create(s, await _user(s, carrier), listing_id, {"price": 150_000, "vehicle_id": vehicle})
    async with uow() as s:
        order = await offers.accept(s, await _user(s, client), offer.id)
    async with uow() as s:
        await orders.confirm(s, await _user(s, carrier), order.id)
        await orders.start(s, await _user(s, carrier), order.id)
        await orders.deliver(s, await _user(s, carrier), order.id)
    async with uow() as s:
        complaint = await orders.complain(s, await _user(s, client), order.id, "LATE", "3 soat kechikdi")
    async with uow() as s:
        o = await s.get(Order, order.id)
        assert o.status == OrderStatus.DISPUTED and o.auto_complete_at is None
        with pytest.raises(DomainError):
            await orders.complete(s, await _user(s, client), order.id)
    assert any(m.key == "admin.complaint" for m in notifier.messages)

    async with uow() as s:
        admin = await s.get(AdminUser, admin_id)
        await orders.resolve_complaint(s, complaint.id, "COMPLETED", "Kechikish tasdiqlandi, ogohlantirish", admin)
    async with uow() as s:
        assert (await s.get(Order, order.id)).status == OrderStatus.COMPLETED
    assert "order.dispute_resolved" in notifier.keys(client)


async def test_permissions_for_carrier_actions():
    plain = await make_user()
    client = await make_user()
    passenger_only, vehicle = await make_carrier(categories=("PASSENGER",))
    listing_id = await passenger_request(client)
    async with uow() as s:
        with pytest.raises(DomainError) as e:  # not a carrier
            await offers.create(s, await _user(s, plain), listing_id, {"price": 150_000})
        assert e.value.code == "no_permission"
    async with uow() as s:
        with pytest.raises(DomainError) as e:  # cannot publish a parcel route without permission
            await listings.create(
                s,
                await _user(s, passenger_only),
                {
                    "kind": "ROUTE", "category": "PARCEL", "from_location_id": await loc("Toshkent"),
                    "to_location_id": await loc("Buxoro"), "departure_at": future(), "price": 50_000,
                    "vehicle_id": vehicle, "capacity_kg": 50,
                },
            )
        assert e.value.code == "no_permission"
    async with uow() as s:
        with pytest.raises(DomainError) as e:
            await offers.create(s, await _user(s, client), listing_id, {"price": 1})
        assert e.value.code == "own_listing"


async def test_unregistered_and_blocked_users_are_rejected():
    guest = await make_user(registered=False)
    blocked = await make_user()
    async with uow() as s:
        (await _user(s, blocked)).is_blocked = True
    for uid, code in ((guest, "not_registered"), (blocked, "user_blocked")):
        with pytest.raises(DomainError) as e:
            await passenger_request(uid)
        assert e.value.code == code


async def test_listing_validation():
    client = await make_user()
    for over, code in [
        ({"departure_at": now() - timedelta(hours=1)}, "departure_in_past"),
        ({"to_location_id": None}, "invalid_input"),
        ({"price": 10}, "invalid_price"),
        ({"from_address": ""}, "address_required"),
        ({"category": "FURNITURE"}, "category_disabled"),
    ]:
        with pytest.raises(DomainError) as e:
            await passenger_request(client, **over)
        assert e.value.code == code, over
