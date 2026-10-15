"""Mutual ratings (TZ §14)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import OrderStatus
from app.models import AdminUser, Review, User
from app.services import audit
from app.services import orders as orders_svc
from app.services.errors import DomainError, not_found


async def create(session: AsyncSession, user: User, order_id: int, rating, text: str | None) -> Review:
    order = await orders_svc.get_for(session, user, order_id)
    if order.status != OrderStatus.COMPLETED:
        raise DomainError("review_not_allowed")
    try:
        rating = int(rating)
    except (TypeError, ValueError):
        raise DomainError("invalid_rating")
    if not 1 <= rating <= 5:
        raise DomainError("invalid_rating")
    exists = await session.scalar(select(Review.id).where(Review.order_id == order.id, Review.author_id == user.id))
    if exists:
        raise DomainError("already_reviewed")
    target_id = order.carrier_id if user.id == order.client_id else order.client_id
    review = Review(
        order_id=order.id, author_id=user.id, target_id=target_id, rating=rating, text=(text or "").strip()[:1000] or None
    )
    session.add(review)
    target = await session.get(User, target_id)
    target.rating_sum += rating
    target.rating_count += 1
    await session.flush()
    return review


async def for_order(session: AsyncSession, order_id: int) -> list[Review]:
    return list((await session.execute(select(Review).where(Review.order_id == order_id))).scalars())


async def about_user(session: AsyncSession, user_id: int, limit: int = 20) -> list[Review]:
    q = (
        select(Review)
        .options(selectinload(Review.author))
        .where(Review.target_id == user_id, Review.is_hidden.is_(False))
        .order_by(Review.created_at.desc())
        .limit(limit)
    )
    return list((await session.execute(q)).scalars())


async def set_hidden(session: AsyncSession, review_id: int, hidden: bool, reason: str, admin: AdminUser) -> None:
    review = await session.get(Review, review_id)
    if review is None:
        raise not_found()
    if review.is_hidden == hidden:
        return
    if hidden and not reason.strip():
        raise DomainError("reason_required")
    target = await session.get(User, review.target_id)
    sign = -1 if hidden else 1
    target.rating_sum += sign * review.rating
    target.rating_count += sign
    review.is_hidden = hidden
    review.hidden_reason = reason.strip() or None
    audit.log_admin(session, admin, "review.hide" if hidden else "review.unhide", "review", review.id, reason=reason)
