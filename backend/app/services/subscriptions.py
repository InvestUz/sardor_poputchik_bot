"""Route subscriptions: "notify me about new matching listings" (TZ §15)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CarrierStatus, Category, ListingKind
from app.models import CarrierPermission, CarrierProfile, Listing, Location, Subscription, User
from app.services import notify
from app.services import settings as settings_svc
from app.services.errors import DomainError, not_found
from app.services.notify import Button
from app.services.users import ensure_active


async def list_for(session: AsyncSession, user: User) -> list[Subscription]:
    q = select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.id)
    return list((await session.execute(q)).scalars())


async def add(session: AsyncSession, user: User, data: dict) -> Subscription:
    ensure_active(user)
    kind, category = data.get("kind"), data.get("category")
    from_id, to_id = data.get("from_location_id"), data.get("to_location_id")
    if kind not in ListingKind.__members__ or category not in Category.__members__:
        raise DomainError("invalid_input")
    if not from_id or not to_id or from_id == to_id:
        raise DomainError("same_locations")
    if await session.get(Location, from_id) is None or await session.get(Location, to_id) is None:
        raise DomainError("invalid_input")
    count = await session.scalar(select(func.count(Subscription.id)).where(Subscription.user_id == user.id))
    if count >= await settings_svc.get(session, "max_subscriptions"):
        raise DomainError("too_many_subscriptions")
    existing = (
        await session.execute(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.kind == kind,
                Subscription.category == category,
                Subscription.from_location_id == from_id,
                Subscription.to_location_id == to_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    sub = Subscription(user_id=user.id, kind=kind, category=category, from_location_id=from_id, to_location_id=to_id)
    session.add(sub)
    await session.flush()
    return sub


async def remove(session: AsyncSession, user: User, sub_id: int) -> None:
    sub = await session.get(Subscription, sub_id)
    if sub is None or sub.user_id != user.id:
        raise not_found()
    await session.delete(sub)


async def notify_matching(session: AsyncSession, listing: Listing) -> None:
    q = (
        select(Subscription.user_id)
        .join(User, User.id == Subscription.user_id)
        .where(
            Subscription.kind == listing.kind,
            Subscription.category == listing.category,
            Subscription.from_location_id == listing.from_location_id,
            Subscription.to_location_id == listing.to_location_id,
            Subscription.user_id != listing.author_id,
            User.is_blocked.is_(False),
        )
    )
    if listing.kind == ListingKind.REQUEST:
        # only carriers who are allowed to serve this category can respond to a client request
        q = (
            q.join(CarrierProfile, CarrierProfile.user_id == Subscription.user_id)
            .join(
                CarrierPermission,
                (CarrierPermission.user_id == Subscription.user_id) & (CarrierPermission.category == listing.category),
            )
            .where(CarrierProfile.status == CarrierStatus.APPROVED)
        )
    for (user_id,) in (await session.execute(q.distinct())).all():
        notify.queue(
            session,
            user_id,
            "listing.matching",
            buttons=[[Button("btn.view", webapp_path=f"/listings/{listing.id}")]],
            listing_id=listing.id,
        )
