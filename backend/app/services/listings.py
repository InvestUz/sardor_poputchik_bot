"""Listings: client requests and carrier routes (TZ §5, §6)."""

from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import exists, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import (
    ACTIVE_ORDER_STATUSES,
    CarrierStatus,
    Category,
    FilePurpose,
    ListingKind,
    ListingStatus,
    OfferStatus,
)
from app.models import (
    AdminUser,
    CarrierPermission,
    CarrierProfile,
    Listing,
    ListingPhoto,
    ListingView,
    Location,
    Offer,
    Order,
    Subscription,
    User,
    Vehicle,
)
from app.services import audit, carriers, notify, subscriptions
from app.services import files as files_svc
from app.services import settings as settings_svc
from app.services.errors import DomainError, forbidden, not_found
from app.services.notify import Button
from app.services.users import ensure_active
from app.timeutil import TASHKENT, now

MIN_PRICE = 1_000
MAX_PRICE = 100_000_000
MAX_PHOTOS = 5
GOODS_PHOTO_OPTIONAL = {Category.DOCUMENTS}


def _text(data: dict, key: str, max_len: int, required: bool = False) -> str | None:
    v = (data.get(key) or "").strip()
    if required and not v:
        raise DomainError("address_required" if "address" in key else f"{key}_required")
    if len(v) > max_len:
        raise DomainError("invalid_input")
    return v or None


def _int(data: dict, key: str, lo: int, hi: int) -> int:
    try:
        v = int(data.get(key))
    except (TypeError, ValueError):
        raise DomainError("invalid_input")
    if not lo <= v <= hi:
        raise DomainError("invalid_input")
    return v


def validate_price(price: Any) -> int:
    try:
        price = int(price)
    except (TypeError, ValueError):
        raise DomainError("invalid_price")
    if not MIN_PRICE <= price <= MAX_PRICE:
        raise DomainError("invalid_price")
    return price


def goods_details(data: dict, category: str) -> dict:
    """Description of a shipment (parcel, documents, furniture, cargo)."""
    d: dict[str, Any] = {
        "description": _text(data, "description", 500, required=True),
        "quantity": _int(data, "quantity", 1, 100),
        "fragile": bool(data.get("fragile")),
    }
    if category != Category.DOCUMENTS:
        d["weight_kg"] = _int(data, "weight_kg", 1, 20000)
        for k in ("length_cm", "width_cm", "height_cm"):
            d[k] = _int(data, k, 1, 1500)
    if category in (Category.FURNITURE, Category.CARGO):
        d["loaders_needed"] = bool(data.get("loaders_needed"))
    return d


def passenger_details(data: dict) -> dict:
    return {
        "passengers": _int(data, "passengers", 1, 8),
        "luggage": _text(data, "luggage", 200, required=True),
        "stops_allowed": bool(data.get("stops_allowed")),
        "whole_car": bool(data.get("whole_car")),
    }


def recipient(data: dict) -> tuple[str, str]:
    name = (data.get("recipient_name") or "").strip()
    phone = (data.get("recipient_phone") or "").strip()
    digits = sum(ch.isdigit() for ch in phone)
    if not name or len(name) > 128 or not 9 <= digits <= 15 or len(phone) > 32:
        raise DomainError("recipient_required")
    return name, phone


async def own_vehicle(session: AsyncSession, user: User, vehicle_id: Any) -> Vehicle:
    v = await session.get(Vehicle, int(vehicle_id)) if vehicle_id else None
    if v is None or v.user_id != user.id or not v.is_active:
        raise DomainError("vehicle_required")
    return v


async def create(session: AsyncSession, user: User, data: dict) -> Listing:
    ensure_active(user)
    cfg = await settings_svc.get_all(session)
    kind, category = data.get("kind"), data.get("category")
    if kind not in ListingKind.__members__ or category not in Category.__members__:
        raise DomainError("invalid_input")
    if category not in cfg["enabled_categories"]:
        raise DomainError("category_disabled")

    active = await session.scalar(
        select(func.count(Listing.id)).where(Listing.author_id == user.id, Listing.status == ListingStatus.PUBLISHED)
    )
    if active >= cfg["max_active_listings"]:
        raise DomainError("too_many_listings")

    from_id, to_id = data.get("from_location_id"), data.get("to_location_id")
    if not from_id or not to_id or await session.get(Location, from_id) is None or await session.get(Location, to_id) is None:
        raise DomainError("invalid_input")
    if from_id == to_id:
        raise DomainError("same_locations")

    departure_at: datetime | None = data.get("departure_at")
    if departure_at is None or departure_at.tzinfo is None:
        raise DomainError("invalid_input")
    if departure_at <= now() or departure_at > now() + timedelta(days=90):
        raise DomainError("departure_in_past")

    listing = Listing(
        author_id=user.id,
        kind=kind,
        category=category,
        status=ListingStatus.PUBLISHED,
        from_location_id=from_id,
        to_location_id=to_id,
        departure_at=departure_at,
        time_flexible=bool(data.get("time_flexible")),
        price=validate_price(data.get("price")),
        comment=_text(data, "comment", 1000),
    )
    photo_ids: list[int] = list(dict.fromkeys(data.get("photo_ids") or []))
    if len(photo_ids) > MAX_PHOTOS:
        raise DomainError("invalid_input")

    if kind == ListingKind.REQUEST:
        listing.capacity_total = 1
        listing.from_address = _text(data, "from_address", 500, required=True)
        listing.to_address = _text(data, "to_address", 500, required=True)
        if category == Category.PASSENGER:
            listing.details = passenger_details(data)
        else:
            listing.details = goods_details(data, category)
            listing.recipient_name, listing.recipient_phone = recipient(data)
            if category not in GOODS_PHOTO_OPTIONAL and not photo_ids:
                raise DomainError("photos_required")
    else:
        if not await carriers.has_permission(session, user, category):
            raise DomainError("no_permission", 403)
        vehicle = await own_vehicle(session, user, data.get("vehicle_id"))
        listing.vehicle_id = vehicle.id
        if category == Category.PASSENGER:
            if vehicle.seats < 1:
                raise DomainError("invalid_vehicle")
            listing.capacity_total = _int(data, "seats", 1, vehicle.seats)
            listing.details = {
                "stops_allowed": bool(data.get("stops_allowed")),
                "luggage": _text(data, "luggage", 200),
            }
        else:
            limit = vehicle.max_weight_kg or 1000
            listing.capacity_total = _int(data, "capacity_kg", 1, limit)
            listing.details = {}

    files = await files_svc.owned_files(session, user, photo_ids, FilePurpose.LISTING_PHOTO)
    session.add(listing)
    await session.flush()
    for f in files:
        session.add(ListingPhoto(listing_id=listing.id, file_id=f.id))
    await subscriptions.notify_matching(session, listing)
    return listing


def load_options():
    return (
        selectinload(Listing.photos),
        selectinload(Listing.author),
        selectinload(Listing.vehicle),
        selectinload(Listing.from_location),
        selectinload(Listing.to_location),
    )


async def get(session: AsyncSession, listing_id: int) -> Listing:
    listing = (
        await session.execute(select(Listing).options(*load_options()).where(Listing.id == listing_id)
            .execution_options(populate_existing=True))
    ).scalar_one_or_none()
    if listing is None:
        raise not_found()
    return listing


async def search(session: AsyncSession, f: dict) -> list[Listing]:
    q = (
        select(Listing)
        .options(*load_options())
        .join(User, User.id == Listing.author_id)
        .where(
            Listing.status == ListingStatus.PUBLISHED,
            Listing.departure_at > now(),
            Listing.capacity_reserved < Listing.capacity_total,
            User.is_blocked.is_(False),
        )
    )
    if f.get("kind"):
        q = q.where(Listing.kind == f["kind"])
    if f.get("category"):
        q = q.where(Listing.category == f["category"])
    if f.get("from_location_id"):
        q = q.where(Listing.from_location_id == f["from_location_id"])
    if f.get("to_location_id"):
        q = q.where(Listing.to_location_id == f["to_location_id"])
    if f.get("date"):
        d: date = f["date"]
        start = datetime.combine(d, time.min, TASHKENT)
        q = q.where(Listing.departure_at >= start, Listing.departure_at < start + timedelta(days=1))
    if f.get("price_min") is not None:
        q = q.where(Listing.price >= f["price_min"])
    if f.get("price_max") is not None:
        q = q.where(Listing.price <= f["price_max"])
    if f.get("min_rating"):
        q = q.where(User.rating_count > 0, User.rating_sum >= f["min_rating"] * User.rating_count)
    if f.get("vehicle_type"):
        q = q.join(Vehicle, Vehicle.id == Listing.vehicle_id).where(Vehicle.vehicle_type == f["vehicle_type"])
    if f.get("min_capacity"):
        q = q.where(Listing.capacity_total - Listing.capacity_reserved >= f["min_capacity"])
    # TZ §6.3: nearest departure first, then newer publications first.
    q = q.order_by(Listing.departure_at.asc(), Listing.created_at.desc())
    q = q.limit(min(int(f.get("limit") or 30), 100)).offset(int(f.get("offset") or 0))
    return list((await session.execute(q)).scalars())


async def mine(session: AsyncSession, user: User) -> list[Listing]:
    q = (
        select(Listing)
        .options(*load_options())
        .where(Listing.author_id == user.id)
        .order_by(Listing.created_at.desc())
        .limit(100)
    )
    return list((await session.execute(q)).scalars())


async def pending_offer_counts(session: AsyncSession, listing_ids: list[int]) -> dict[int, int]:
    if not listing_ids:
        return {}
    rows = await session.execute(
        select(Offer.listing_id, func.count(Offer.id))
        .where(Offer.listing_id.in_(listing_ids), Offer.status == OfferStatus.PENDING)
        .group_by(Offer.listing_id)
    )
    return {lid: n for lid, n in rows}


# ---------------------------------------------------------------- author's live activity

ACTIVITY_ROUTE_DAYS = 30


async def record_view(session: AsyncSession, listing: Listing, user: User) -> None:
    """Remembers that a non-author opened the listing (idempotent, safe under concurrent requests)."""
    if listing.author_id == user.id:
        return
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    await session.execute(
        insert(ListingView)
        .values(listing_id=listing.id, user_id=user.id, created_at=now())
        .on_conflict_do_nothing(index_elements=["listing_id", "user_id"])
    )


async def activity(session: AsyncSession, user: User, listing_id: int) -> dict:
    listing = await session.get(Listing, listing_id)
    if listing is None:
        raise not_found()
    if listing.author_id != user.id:
        raise forbidden()
    viewed = await session.scalar(select(func.count(ListingView.id)).where(ListingView.listing_id == listing.id))
    same_route = (
        lambda m: (m.category == listing.category)
        & (m.from_location_id == listing.from_location_id)
        & (m.to_location_id == listing.to_location_id)
    )
    subscribed = exists().where(Subscription.user_id == User.id, same_route(Subscription))
    recent_route = exists().where(
        Listing.author_id == User.id,
        Listing.kind == ListingKind.ROUTE,
        Listing.departure_at >= now() - timedelta(days=ACTIVITY_ROUTE_DAYS),
        same_route(Listing),
    )
    carriers_on_route = await session.scalar(
        select(func.count(func.distinct(User.id)))
        .join(CarrierProfile, CarrierProfile.user_id == User.id)
        .join(CarrierPermission, CarrierPermission.user_id == User.id)
        .where(
            CarrierProfile.status == CarrierStatus.APPROVED,
            CarrierPermission.category == listing.category,
            User.is_blocked.is_(False),
            User.id != listing.author_id,
            subscribed | recent_route,
        )
    )
    return {"carriers_on_route": carriers_on_route or 0, "viewed": viewed or 0}


async def reserve(session: AsyncSession, listing_id: int, qty: int) -> bool:
    """Atomically reserve capacity; returns False when not enough is left (TZ §7: no double booking)."""
    res = await session.execute(
        update(Listing)
        .where(
            Listing.id == listing_id,
            Listing.status == ListingStatus.PUBLISHED,
            Listing.capacity_reserved + qty <= Listing.capacity_total,
        )
        .values(capacity_reserved=Listing.capacity_reserved + qty)
        .execution_options(synchronize_session=False)
    )
    return res.rowcount == 1


async def release(session: AsyncSession, listing_id: int, qty: int) -> None:
    await session.execute(
        update(Listing)
        .where(Listing.id == listing_id, Listing.capacity_reserved >= qty)
        .values(capacity_reserved=Listing.capacity_reserved - qty)
        .execution_options(synchronize_session=False)
    )


async def close_pending_offers(session: AsyncSession, listing: Listing, status: str, except_offer_id: int | None = None):
    q = select(Offer).where(Offer.listing_id == listing.id, Offer.status == OfferStatus.PENDING)
    for offer in (await session.execute(q)).scalars():
        if offer.id == except_offer_id:
            continue
        offer.status = status
        offer.decided_at = now()
        notify.queue(session, offer.counterparty_id, "offer.closed", listing_id=listing.id)


async def cancel(session: AsyncSession, user: User, listing_id: int) -> Listing:
    listing = await get(session, listing_id)
    if listing.author_id != user.id:
        raise forbidden()
    await _cancel(session, listing)
    return listing


async def admin_cancel(session: AsyncSession, listing_id: int, reason: str, admin: AdminUser) -> None:
    listing = await get(session, listing_id)
    await _cancel(session, listing)
    audit.log_admin(session, admin, "listing.cancel", "listing", listing.id, reason=reason)
    notify.queue(session, listing.author_id, "listing.cancelled_by_admin", listing_id=listing.id, reason=reason)


async def _cancel(session: AsyncSession, listing: Listing) -> None:
    if listing.status != ListingStatus.PUBLISHED:
        raise DomainError("listing_not_active")
    active = await session.scalar(
        select(func.count(Order.id)).where(Order.listing_id == listing.id, Order.status.in_(ACTIVE_ORDER_STATUSES))
    )
    if active:
        raise DomainError("listing_has_active_orders")
    listing.status = ListingStatus.CANCELLED
    listing.closed_at = now()
    await close_pending_offers(session, listing, OfferStatus.AUTO_CLOSED)


def open_button(listing_id: int) -> list[list[Button]]:
    return [[Button("btn.view", webapp_path=f"/listings/{listing_id}")]]
