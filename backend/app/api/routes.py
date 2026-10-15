"""REST API for the Telegram Mini App. Every handler is its own unit of work."""

from datetime import date

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse

from app.api import serializers as ser
from app.api.deps import current_user, tg_user
from app.api.schemas import (
    CounterIn,
    DeliverIn,
    DocumentIn,
    ListingIn,
    MeIn,
    OfferIn,
    ReasonIn,
    ReviewIn,
    SubmitIn,
    SubscriptionIn,
    VehicleIn,
)
from app.config import settings
from app.db import uow
from app.enums import CANCEL_REASONS, COMPLAINT_REASONS, Category, DocumentKind, VehicleType
from sqlalchemy import select

from app.models import CarrierProfile, StoredFile
from app.services import (
    carriers,
    files,
    listings,
    locations,
    offers,
    orders,
    pricing,
    profiles,
    reviews,
    subscriptions,
    users,
)
from app.services import settings as settings_svc
from app.services.errors import DomainError, not_found

router = APIRouter(prefix="/api")
Tg = Depends(tg_user)


async def _stats(s, user_ids) -> dict[int, dict]:
    """trips / verified for every user shown in one response (single batch, no N+1)."""
    return await profiles.public_stats(s, user_ids)


# ------------------------------------------------------------------ profile & reference data


@router.get("/me")
async def me(tg: dict = Tg):
    async with uow() as s:
        user = await users.get_by_telegram_id(s, int(tg["id"]))
        if user is None:
            return {"registered": False}
        profile = (
            await s.execute(select(CarrierProfile).where(CarrierProfile.user_id == user.id))
        ).scalar_one_or_none()
        return {
            "registered": user.is_registered,
            "blocked": user.is_blocked,
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "lang": user.lang,
            "rating": user.rating,
            "rating_count": user.rating_count,
            "carrier": {
                "status": profile.status if profile else "DRAFT",
                "full_name": profile.full_name if profile else None,
                "admin_comment": profile.admin_comment if profile else None,
                "permissions": await carriers.permissions(s, user.id),
            },
        }


@router.patch("/me")
async def update_me(body: MeIn, tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        users.set_lang(user, body.lang)
    return {"ok": True}


@router.get("/config")
async def config(tg: dict = Tg):
    async with uow() as s:
        cfg = await settings_svc.get_all(s)
    return {
        "enabled_categories": cfg["enabled_categories"],
        "all_categories": [c.value for c in Category],
        "required_documents": cfg["required_documents"],
        "document_kinds": [d.value for d in DocumentKind],
        "vehicle_types": [v.value for v in VehicleType],
        "cancel_reasons": CANCEL_REASONS,
        "complaint_reasons": COMPLAINT_REASONS,
        "support_contact": cfg["support_contact"],
        "commission_percent": cfg["commission_percent"],
    }


@router.get("/locations")
async def list_locations(tg: dict = Tg):
    async with uow() as s:
        return [ser.location(l) for l in await locations.all_(s)]


@router.get("/price-hint")
async def price_hint(category: str, from_location_id: int, to_location_id: int, seats: int = 1, tg: dict = Tg):
    async with uow() as s:
        await current_user(s, tg)
        return await pricing.hint(s, category, from_location_id, to_location_id, seats)


@router.get("/users/{user_id}")
async def user_profile(user_id: int, tg: dict = Tg):
    async with uow() as s:
        await current_user(s, tg)
        return ser.user_profile(await profiles.profile(s, user_id))


@router.get("/users/{user_id}/reviews")
async def user_reviews(user_id: int, tg: dict = Tg):
    async with uow() as s:
        await current_user(s, tg)
        return [
            {"rating": r.rating, "text": r.text, "author": r.author.first_name, "created_at": r.created_at.isoformat()}
            for r in await reviews.about_user(s, user_id)
        ]


# ------------------------------------------------------------------ files


@router.post("/files")
async def upload(purpose: str = Form(...), file: UploadFile = File(...), tg: dict = Tg):
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    async with uow() as s:
        user = await current_user(s, tg)
        f = await files.save_upload(s, user, data, purpose)
        return {"id": f.id}


@router.get("/files/{file_id}")
async def download(file_id: int, tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        f = await s.get(StoredFile, file_id)
        if f is None or not await files.can_access(s, user, f):
            raise not_found()
        path = files.full_path(f)
    return FileResponse(path, media_type=f.mime, headers={"Cache-Control": "private, max-age=86400"})


# ------------------------------------------------------------------ carrier verification


@router.get("/carrier")
async def carrier_profile(tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        profile = await carriers.get_or_create_profile(s, user)
        return {
            "status": profile.status,
            "full_name": profile.full_name,
            "admin_comment": profile.admin_comment,
            "permissions": await carriers.permissions(s, user.id),
            "vehicles": [ser.vehicle(v, with_plate=True) for v in await carriers.vehicles(s, user)],
            "documents": [{"id": d.id, "kind": d.kind, "file_id": d.file_id} for d in await carriers.documents(s, user.id)],
        }


@router.post("/carrier/vehicles")
async def add_vehicle(body: VehicleIn, tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        v = await carriers.add_vehicle(s, user, body.model_dump())
        return ser.vehicle(v, with_plate=True)


@router.delete("/carrier/vehicles/{vehicle_id}")
async def remove_vehicle(vehicle_id: int, tg: dict = Tg):
    async with uow() as s:
        await carriers.remove_vehicle(s, await current_user(s, tg), vehicle_id)
    return {"ok": True}


@router.post("/carrier/documents")
async def add_document(body: DocumentIn, tg: dict = Tg):
    async with uow() as s:
        d = await carriers.add_document(s, await current_user(s, tg), body.kind, body.file_id)
        return {"id": d.id, "kind": d.kind, "file_id": d.file_id}


@router.delete("/carrier/documents/{doc_id}")
async def remove_document(doc_id: int, tg: dict = Tg):
    async with uow() as s:
        await carriers.remove_document(s, await current_user(s, tg), doc_id)
    return {"ok": True}


@router.post("/carrier/submit")
async def submit_carrier(body: SubmitIn, tg: dict = Tg):
    async with uow() as s:
        profile = await carriers.submit(s, await current_user(s, tg), body.full_name)
        return {"status": profile.status}


# ------------------------------------------------------------------ listings


@router.get("/listings")
async def search_listings(
    kind: str | None = None,
    category: str | None = None,
    from_location_id: int | None = None,
    to_location_id: int | None = None,
    date: date | None = None,
    price_min: int | None = None,
    price_max: int | None = None,
    min_rating: float | None = None,
    vehicle_type: str | None = None,
    min_capacity: int | None = None,
    limit: int = 30,
    offset: int = 0,
    tg: dict = Tg,
):
    filters = locals().copy()
    filters.pop("tg")
    async with uow() as s:
        user = await current_user(s, tg)
        items = await listings.search(s, filters)
        stats = await _stats(s, [l.author_id for l in items])
        return [ser.listing(l, user.id, stats=stats) for l in items]


@router.post("/listings")
async def create_listing(body: ListingIn, tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        listing = await listings.create(s, user, body.model_dump())
        listing = await listings.get(s, listing.id)
        return ser.listing(listing, user.id, pending_offers=0, stats=await _stats(s, [user.id]))


@router.get("/my/listings")
async def my_listings(tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        items = await listings.mine(s, user)
        counts = await listings.pending_offer_counts(s, [l.id for l in items])
        stats = await _stats(s, [user.id])
        return [ser.listing(l, user.id, pending_offers=counts.get(l.id, 0), stats=stats) for l in items]


@router.get("/listings/{listing_id}")
async def get_listing(listing_id: int, tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        listing = await listings.get(s, listing_id)
        counts = await listings.pending_offer_counts(s, [listing.id]) if listing.author_id == user.id else {}
        await listings.record_view(s, listing, user)
        stats = await _stats(s, [listing.author_id])
        return ser.listing(listing, user.id, pending_offers=counts.get(listing.id, 0), stats=stats)


@router.get("/listings/{listing_id}/activity")
async def listing_activity(listing_id: int, tg: dict = Tg):
    async with uow() as s:
        return await listings.activity(s, await current_user(s, tg), listing_id)


@router.post("/listings/{listing_id}/cancel")
async def cancel_listing(listing_id: int, tg: dict = Tg):
    async with uow() as s:
        await listings.cancel(s, await current_user(s, tg), listing_id)
    return {"ok": True}


# ------------------------------------------------------------------ offers


@router.get("/listings/{listing_id}/offers")
async def listing_offers(listing_id: int, tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        items = await offers.for_listing(s, user, listing_id)
        stats = await _stats(s, [o.counterparty_id for o in items])
        return [ser.offer(o, user.id, stats) for o in items]


@router.post("/listings/{listing_id}/offers")
async def make_offer(listing_id: int, body: OfferIn, tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        o = await offers.create(s, user, listing_id, body.model_dump())
        return ser.offer(await offers.get_view(s, o.id), user.id, await _stats(s, [o.counterparty_id]))


@router.get("/my/offers")
async def my_offers(tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        items = await offers.mine(s, user)
        stats = await _stats(s, [o.counterparty_id for o in items])
        return [ser.offer(o, user.id, stats) for o in items]


@router.post("/offers/{offer_id}/counter")
async def counter_offer(offer_id: int, body: CounterIn, tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        o = await offers.counter(s, user, offer_id, body.price, body.comment)
        return ser.offer(await offers.get_view(s, o.id), user.id, await _stats(s, [o.counterparty_id]))


@router.post("/offers/{offer_id}/accept")
async def accept_offer(offer_id: int, tg: dict = Tg):
    async with uow() as s:
        order = await offers.accept(s, await current_user(s, tg), offer_id)
        return {"order_id": order.id, "status": order.status}


@router.post("/offers/{offer_id}/reject")
async def reject_offer(offer_id: int, tg: dict = Tg):
    async with uow() as s:
        await offers.reject(s, await current_user(s, tg), offer_id)
    return {"ok": True}


@router.post("/offers/{offer_id}/withdraw")
async def withdraw_offer(offer_id: int, tg: dict = Tg):
    async with uow() as s:
        await offers.withdraw(s, await current_user(s, tg), offer_id)
    return {"ok": True}


# ------------------------------------------------------------------ orders


@router.get("/my/orders")
async def my_orders(tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        items = await orders.mine(s, user)
        stats = await _stats(s, [o.carrier_id if o.client_id == user.id else o.client_id for o in items])
        return [ser.order_brief(o, user.id, stats) for o in items]


async def _order_view(s, user, order_id: int) -> dict:
    order = await orders.get_for(s, user, order_id)
    other_id = order.carrier_id if order.client_id == user.id else order.client_id
    return ser.order(
        order,
        user.id,
        await reviews.for_order(s, order.id),
        stats=await _stats(s, [other_id]),
        history=await orders.history(s, order.id),
    )


@router.get("/orders/{order_id}")
async def get_order(order_id: int, tg: dict = Tg):
    async with uow() as s:
        return await _order_view(s, await current_user(s, tg), order_id)


@router.post("/orders/{order_id}/cancel")
async def cancel_order(order_id: int, body: ReasonIn, tg: dict = Tg):
    async with uow() as s:
        await orders.cancel(s, await current_user(s, tg), order_id, body.reason_code, body.text)
    async with uow() as s:
        return await _order_view(s, await current_user(s, tg), order_id)


@router.post("/orders/{order_id}/complain")
async def complain(order_id: int, body: ReasonIn, tg: dict = Tg):
    async with uow() as s:
        await orders.complain(s, await current_user(s, tg), order_id, body.reason_code, body.text)
    async with uow() as s:
        return await _order_view(s, await current_user(s, tg), order_id)


@router.post("/orders/{order_id}/review")
async def review(order_id: int, body: ReviewIn, tg: dict = Tg):
    async with uow() as s:
        await reviews.create(s, await current_user(s, tg), order_id, body.rating, body.text)
    async with uow() as s:
        return await _order_view(s, await current_user(s, tg), order_id)


@router.post("/orders/{order_id}/deliver")
async def deliver_order(order_id: int, body: DeliverIn | None = Body(None), tg: dict = Tg):
    """Parcels need the handover code from the recipient: {"code": "4821"}; passenger orders need no body."""
    async with uow() as s:
        await orders.deliver(s, await current_user(s, tg), order_id, body.code if body else None)
    async with uow() as s:
        return await _order_view(s, await current_user(s, tg), order_id)


_SIMPLE_ACTIONS = {  # "deliver" has its own route above (optional code body)
    "confirm": orders.confirm,
    "start": orders.start,
    "complete": orders.complete,
}


@router.post("/orders/{order_id}/{action}")
async def order_action(order_id: int, action: str, tg: dict = Tg):
    fn = _SIMPLE_ACTIONS.get(action)
    if fn is None:
        raise not_found()
    async with uow() as s:
        user = await current_user(s, tg)
        await fn(s, user, order_id)
    async with uow() as s:
        return await _order_view(s, await current_user(s, tg), order_id)


# ------------------------------------------------------------------ subscriptions


@router.get("/subscriptions")
async def list_subscriptions(tg: dict = Tg):
    async with uow() as s:
        user = await current_user(s, tg)
        return [
            {"id": x.id, "kind": x.kind, "category": x.category,
             "from_location_id": x.from_location_id, "to_location_id": x.to_location_id}
            for x in await subscriptions.list_for(s, user)
        ]


@router.post("/subscriptions")
async def add_subscription(body: SubscriptionIn, tg: dict = Tg):
    async with uow() as s:
        sub = await subscriptions.add(s, await current_user(s, tg), body.model_dump())
        return {"id": sub.id}


@router.delete("/subscriptions/{sub_id}")
async def remove_subscription(sub_id: int, tg: dict = Tg):
    async with uow() as s:
        await subscriptions.remove(s, await current_user(s, tg), sub_id)
    return {"ok": True}


__all__ = ["router", "DomainError"]
