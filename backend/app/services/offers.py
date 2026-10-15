"""Offers and counter-offers (TZ §7)."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import Category, FilePurpose, ListingKind, ListingStatus, OfferStatus
from app.models import Listing, Offer, OfferPhoto, Order, User
from app.services import carriers, listings, notify, orders
from app.services import files as files_svc
from app.services import settings as settings_svc
from app.services.errors import DomainError, forbidden, not_found
from app.services.notify import Button
from app.services.users import ensure_active
from app.timeutil import now


def offer_buttons(offer_id: int, listing_id: int) -> list[list[Button]]:
    return [
        [Button("btn.accept", callback=f"of:accept:{offer_id}"), Button("btn.reject", callback=f"of:reject:{offer_id}")],
        [Button("btn.view", webapp_path=f"/listings/{listing_id}")],
    ]


async def _expires_at(session: AsyncSession, listing: Listing):
    ttl = await settings_svc.get(session, "offer_ttl_minutes")
    return min(now() + timedelta(minutes=ttl), listing.departure_at)


def _ensure_listing_open(listing: Listing) -> None:
    if listing.status != ListingStatus.PUBLISHED or listing.departure_at <= now():
        raise DomainError("listing_not_active")


async def get(session: AsyncSession, offer_id: int) -> Offer:
    offer = (
        await session.execute(
            select(Offer)
            .options(selectinload(Offer.listing), selectinload(Offer.photos))
            .where(Offer.id == offer_id)
        )
    ).scalar_one_or_none()
    if offer is None:
        raise not_found()
    return offer


def other_party(offer: Offer, user_id: int) -> int:
    return offer.counterparty_id if user_id == offer.listing.author_id else offer.listing.author_id


def _ensure_participant(offer: Offer, user: User) -> None:
    if user.id not in (offer.counterparty_id, offer.listing.author_id):
        raise forbidden()


def _ensure_live(offer: Offer) -> None:
    if offer.status != OfferStatus.PENDING:
        raise DomainError("offer_not_pending")
    if offer.expires_at <= now():
        raise DomainError("offer_expired")


def _ensure_responder(offer: Offer, user: User) -> None:
    """Only the side that did NOT make the current proposal may accept / reject / counter it."""
    _ensure_participant(offer, user)
    if offer.proposed_by_id == user.id:
        raise DomainError("not_your_turn")


async def create(session: AsyncSession, user: User, listing_id: int, data: dict) -> Offer:
    ensure_active(user)
    listing = await listings.get(session, listing_id)
    _ensure_listing_open(listing)
    if listing.author_id == user.id:
        raise DomainError("own_listing")
    if listing.author.is_blocked:
        raise DomainError("listing_not_active")
    existing = await session.scalar(
        select(Offer.id).where(
            Offer.listing_id == listing.id, Offer.counterparty_id == user.id, Offer.status == OfferStatus.PENDING
        )
    )
    if existing:
        raise DomainError("offer_exists")

    offer = Offer(
        listing_id=listing.id,
        counterparty_id=user.id,
        proposed_by_id=user.id,
        price=listings.validate_price(data.get("price")),
        comment=listings._text(data, "comment", 1000),
        expires_at=await _expires_at(session, listing),
        status=OfferStatus.PENDING,
    )
    photo_ids: list[int] = []

    if listing.kind == ListingKind.REQUEST:
        # a carrier responds to a client's request
        if not await carriers.has_permission(session, user, listing.category):
            raise DomainError("no_permission", 403)
        offer.vehicle_id = (await listings.own_vehicle(session, user, data.get("vehicle_id"))).id
        offer.quantity = 1
        if listing.capacity_available < 1:
            raise DomainError("no_capacity")
    else:
        # a client books space on a carrier's route
        offer.from_address = listings._text(data, "from_address", 500, required=True)
        offer.to_address = listings._text(data, "to_address", 500, required=True)
        if listing.category == Category.PASSENGER:
            details = listings.passenger_details(data)
            offer.quantity = details["passengers"]
        else:
            details = listings.goods_details(data, listing.category)
            offer.quantity = details.get("weight_kg", 1)
            offer.recipient_name, offer.recipient_phone = listings.recipient(data)
            photo_ids = list(dict.fromkeys(data.get("photo_ids") or []))
            if listing.category not in listings.GOODS_PHOTO_OPTIONAL and not photo_ids:
                raise DomainError("photos_required")
            if len(photo_ids) > listings.MAX_PHOTOS:
                raise DomainError("invalid_input")
        offer.details = details
        if offer.quantity > listing.capacity_available:
            raise DomainError("no_capacity")

    files = await files_svc.owned_files(session, user, photo_ids, FilePurpose.OFFER_PHOTO)
    session.add(offer)
    await session.flush()
    for f in files:
        session.add(OfferPhoto(offer_id=offer.id, file_id=f.id))
    notify.queue(
        session,
        listing.author_id,
        "offer.new",
        buttons=offer_buttons(offer.id, listing.id),
        listing_id=listing.id,
        price=offer.price,
        from_name=user.display_name,
    )
    return offer


async def counter(session: AsyncSession, user: User, offer_id: int, price, comment: str | None) -> Offer:
    ensure_active(user)
    offer = await get(session, offer_id)
    _ensure_responder(offer, user)
    _ensure_live(offer)
    _ensure_listing_open(offer.listing)
    offer.status = OfferStatus.COUNTERED
    offer.decided_at = now()
    new = Offer(
        listing_id=offer.listing_id,
        counterparty_id=offer.counterparty_id,
        proposed_by_id=user.id,
        parent_id=offer.id,
        price=listings.validate_price(price),
        quantity=offer.quantity,
        vehicle_id=offer.vehicle_id,
        details=offer.details,
        comment=(comment or "").strip()[:1000] or None,
        from_address=offer.from_address,
        to_address=offer.to_address,
        recipient_name=offer.recipient_name,
        recipient_phone=offer.recipient_phone,
        expires_at=await _expires_at(session, offer.listing),
        status=OfferStatus.PENDING,
    )
    session.add(new)
    await session.flush()
    for p in offer.photos:
        session.add(OfferPhoto(offer_id=new.id, file_id=p.file_id))
    notify.queue(
        session,
        other_party(offer, user.id),
        "offer.countered",
        buttons=offer_buttons(new.id, offer.listing_id),
        listing_id=offer.listing_id,
        price=new.price,
    )
    return new


async def accept(session: AsyncSession, user: User, offer_id: int) -> Order:
    ensure_active(user)
    offer = await get(session, offer_id)
    _ensure_responder(offer, user)
    _ensure_live(offer)
    listing = offer.listing
    _ensure_listing_open(listing)
    if not await listings.reserve(session, listing.id, offer.quantity):
        raise DomainError("no_capacity")
    await session.refresh(listing)
    offer.status = OfferStatus.ACCEPTED
    offer.decided_at = now()
    return await orders.create_from_offer(session, offer, listing, accepted_by=user)


async def reject(session: AsyncSession, user: User, offer_id: int) -> Offer:
    offer = await get(session, offer_id)
    _ensure_responder(offer, user)
    _ensure_live(offer)
    offer.status = OfferStatus.REJECTED
    offer.decided_at = now()
    notify.queue(session, offer.proposed_by_id, "offer.rejected", listing_id=offer.listing_id)
    return offer


async def withdraw(session: AsyncSession, user: User, offer_id: int) -> Offer:
    offer = await get(session, offer_id)
    _ensure_participant(offer, user)
    if offer.proposed_by_id != user.id:
        raise DomainError("not_your_turn")
    if offer.status != OfferStatus.PENDING:
        raise DomainError("offer_not_pending")
    offer.status = OfferStatus.WITHDRAWN
    offer.decided_at = now()
    notify.queue(session, other_party(offer, user.id), "offer.withdrawn", listing_id=offer.listing_id)
    return offer


def _view_options():
    return (
        selectinload(Offer.listing).selectinload(Listing.from_location),
        selectinload(Offer.listing).selectinload(Listing.to_location),
        selectinload(Offer.counterparty),
        selectinload(Offer.vehicle),
        selectinload(Offer.photos),
    )


async def get_view(session: AsyncSession, offer_id: int) -> Offer:
    q = select(Offer).options(*_view_options()).where(Offer.id == offer_id).execution_options(populate_existing=True)
    return (await session.execute(q)).scalar_one()


async def for_listing(session: AsyncSession, user: User, listing_id: int) -> list[Offer]:
    listing = await session.get(Listing, listing_id)
    if listing is None:
        raise not_found()
    q = (
        select(Offer)
        .options(*_view_options())
        .where(Offer.listing_id == listing_id)
        .order_by(Offer.created_at.desc())
    )
    if listing.author_id != user.id:
        q = q.where(Offer.counterparty_id == user.id)
    return list((await session.execute(q)).scalars())


async def mine(session: AsyncSession, user: User) -> list[Offer]:
    """Offers in threads where the user is the non-author side (i.e. offers the user sent)."""
    q = (
        select(Offer)
        .options(*_view_options())
        .where(Offer.counterparty_id == user.id, Offer.status != OfferStatus.COUNTERED)
        .order_by(Offer.created_at.desc())
        .limit(100)
    )
    return list((await session.execute(q)).scalars())
