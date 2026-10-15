"""Order lifecycle (TZ §9, §12, §13). Every transition is validated here and journaled."""

import secrets
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.enums import (
    CANCEL_REASONS,
    COMPLAINT_REASONS,
    ActorType,
    Category,
    ComplaintStatus,
    ListingKind,
    ListingStatus,
    OfferStatus,
    OrderStatus,
)
from app.models import (
    AdminUser,
    Cancellation,
    Complaint,
    Listing,
    Offer,
    Order,
    OrderStatusHistory,
    User,
)
from app.services import audit, notify
from app.services import listings as listings_svc
from app.services import settings as settings_svc
from app.services.errors import DomainError, forbidden, not_found
from app.services.notify import Button
from app.services.users import ensure_active
from app.timeutil import now

S = OrderStatus

TRANSITIONS: dict[str, set[str]] = {
    S.AWAITING_CONFIRMATION: {S.CONFIRMED, S.CANCELLED},
    S.CONFIRMED: {S.IN_PROGRESS, S.CANCELLED, S.DISPUTED},
    S.IN_PROGRESS: {S.AWAITING_COMPLETION, S.DISPUTED},
    S.AWAITING_COMPLETION: {S.COMPLETED, S.DISPUTED},
    S.DISPUTED: {S.COMPLETED, S.CANCELLED},
}

USER_CANCELLABLE = {S.AWAITING_CONFIRMATION, S.CONFIRMED}
DELIVERY_CODE_MAX_ATTEMPTS = 5
# the client sees the parcel handover code while the parcel is on its way (or under dispute)
DELIVERY_CODE_VISIBLE = {S.CONFIRMED, S.IN_PROGRESS, S.AWAITING_COMPLETION, S.DISPUTED}
COMPLAINABLE = {S.CONFIRMED, S.IN_PROGRESS, S.AWAITING_COMPLETION}


def view_button(order_id: int, text_key: str = "btn.view") -> Button:
    return Button(text_key, webapp_path=f"/orders/{order_id}")


def _transition(session: AsyncSession, order: Order, to: str, actor: ActorType, actor_id: int | None, reason=None):
    if to not in TRANSITIONS.get(order.status, set()):
        raise DomainError("invalid_transition")
    session.add(
        OrderStatusHistory(
            order_id=order.id, from_status=order.status, to_status=to, actor_type=actor, actor_id=actor_id, reason=reason
        )
    )
    order.status = to


async def get(session: AsyncSession, order_id: int) -> Order:
    order = (
        await session.execute(
            select(Order)
            .options(
                selectinload(Order.listing),
                selectinload(Order.client),
                selectinload(Order.carrier),
                selectinload(Order.vehicle),
                selectinload(Order.from_location),
                selectinload(Order.to_location),
            )
            .where(Order.id == order_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if order is None:
        raise not_found()
    return order


async def get_for(session: AsyncSession, user: User, order_id: int) -> Order:
    order = await get(session, order_id)
    if user.id not in (order.client_id, order.carrier_id):
        raise forbidden()
    return order


async def mine(session: AsyncSession, user: User) -> list[Order]:
    q = (
        select(Order)
        .options(
            selectinload(Order.client),
            selectinload(Order.carrier),
            selectinload(Order.from_location),
            selectinload(Order.to_location),
        )
        .where(or_(Order.client_id == user.id, Order.carrier_id == user.id))
        .order_by(Order.created_at.desc())
        .limit(100)
    )
    return list((await session.execute(q)).scalars())


async def history(session: AsyncSession, order_id: int) -> list[OrderStatusHistory]:
    q = select(OrderStatusHistory).where(OrderStatusHistory.order_id == order_id).order_by(OrderStatusHistory.id)
    return list((await session.execute(q)).scalars())


def timeline(entries: list[OrderStatusHistory]) -> list[dict]:
    """First time the order reached each status, in order of occurrence."""
    seen: dict[str, OrderStatusHistory] = {}
    for h in entries:
        seen.setdefault(h.to_status, h)
    return [{"status": st, "at": h.created_at.isoformat()} for st, h in seen.items()]


def needs_delivery_code(order: Order) -> bool:
    return order.delivery_code is not None


def code_attempts_left(order: Order) -> int | None:
    if order.delivery_code is None:
        return None
    return max(0, DELIVERY_CODE_MAX_ATTEMPTS - (order.delivery_code_attempts or 0))


# ---------------------------------------------------------------- creation / confirmation


async def create_from_offer(session: AsyncSession, offer: Offer, listing: Listing, accepted_by: User) -> Order:
    cfg = await settings_svc.get_all(session)
    is_request = listing.kind == ListingKind.REQUEST
    client_id = listing.author_id if is_request else offer.counterparty_id
    carrier_id = offer.counterparty_id if is_request else listing.author_id
    src = listing if is_request else offer
    percent = float(cfg["commission_percent"])
    order = Order(
        listing_id=listing.id,
        offer_id=offer.id,
        client_id=client_id,
        carrier_id=carrier_id,
        vehicle_id=offer.vehicle_id if is_request else listing.vehicle_id,
        category=listing.category,
        status=S.AWAITING_CONFIRMATION,
        price=offer.price,
        quantity=offer.quantity,
        commission_percent=percent,
        estimated_commission=round(offer.price * percent / 100),
        from_location_id=listing.from_location_id,
        to_location_id=listing.to_location_id,
        departure_at=listing.departure_at,
        from_address=src.from_address,
        to_address=src.to_address,
        recipient_name=src.recipient_name,
        recipient_phone=src.recipient_phone,
        details=dict(src.details or {}),
    )
    session.add(order)
    await session.flush()
    session.add(
        OrderStatusHistory(
            order_id=order.id, to_status=S.AWAITING_CONFIRMATION, actor_type=ActorType.USER, actor_id=accepted_by.id
        )
    )

    if accepted_by.id == carrier_id:
        # the carrier accepted the client's proposal: both sides have now agreed, no extra step
        _transition(session, order, S.CONFIRMED, ActorType.USER, carrier_id)
        await _on_confirmed(session, order, listing)
    else:
        order.confirm_deadline = now() + timedelta(minutes=cfg["confirm_timeout_minutes"])
        notify.queue(
            session,
            carrier_id,
            "order.awaiting_confirmation",
            buttons=[
                [Button("btn.confirm", callback=f"o:confirm:{order.id}"), Button("btn.cancel", webapp_path=f"/orders/{order.id}")]
            ],
            order_id=order.id,
            minutes=cfg["confirm_timeout_minutes"],
        )
        notify.queue(session, client_id, "order.waiting_carrier", buttons=[[view_button(order.id)]], order_id=order.id)
    return order


async def _on_confirmed(session: AsyncSession, order: Order, listing: Listing) -> None:
    order.confirmed_at = now()
    order.confirm_deadline = None
    if listing.kind == ListingKind.REQUEST:
        listing.status = ListingStatus.CLOSED
        listing.closed_at = now()
        await listings_svc.close_pending_offers(session, listing, OfferStatus.AUTO_CLOSED)
    else:
        await session.refresh(listing)
        q = select(Offer).where(
            Offer.listing_id == listing.id,
            Offer.status == OfferStatus.PENDING,
            Offer.quantity > listing.capacity_available,
        )
        for offer in (await session.execute(q)).scalars():
            offer.status = OfferStatus.AUTO_CLOSED
            offer.decided_at = now()
            notify.queue(session, offer.counterparty_id, "offer.closed", listing_id=listing.id)
    for uid in (order.client_id, order.carrier_id):
        notify.queue(session, uid, "order.confirmed", buttons=[[view_button(order.id, "btn.contacts")]], order_id=order.id)
    if order.category != Category.PASSENGER and order.delivery_code is None:
        # parcel handover: the client tells the code to the recipient, the carrier enters it on delivery
        order.delivery_code = f"{secrets.randbelow(10_000):04d}"
        order.delivery_code_attempts = 0
        notify.queue(
            session,
            order.client_id,
            "order.delivery_code",
            buttons=[[view_button(order.id)]],
            order_id=order.id,
            code=order.delivery_code,
        )


async def confirm(session: AsyncSession, user: User, order_id: int) -> Order:
    ensure_active(user)
    order = await get_for(session, user, order_id)
    if order.carrier_id != user.id:
        raise forbidden()
    if order.status != S.AWAITING_CONFIRMATION:
        raise DomainError("invalid_transition")
    if order.confirm_deadline and order.confirm_deadline < now():
        raise DomainError("confirm_deadline_passed")
    _transition(session, order, S.CONFIRMED, ActorType.USER, user.id)
    await _on_confirmed(session, order, order.listing)
    return order


# ---------------------------------------------------------------- execution


async def start(session: AsyncSession, user: User, order_id: int) -> Order:
    order = await get_for(session, user, order_id)
    if order.carrier_id != user.id:
        raise forbidden()
    _transition(session, order, S.IN_PROGRESS, ActorType.USER, user.id)
    order.started_at = now()
    notify.queue(session, order.client_id, "order.started", buttons=[[view_button(order.id)]], order_id=order.id)
    return order


async def deliver(session: AsyncSession, user: User, order_id: int, code: str | None = None) -> Order:
    order = await get_for(session, user, order_id)
    if order.carrier_id != user.id:
        raise forbidden()
    if S.AWAITING_COMPLETION not in TRANSITIONS.get(order.status, set()):
        raise DomainError("invalid_transition")
    if needs_delivery_code(order):
        _check_delivery_code(order, code)
    _transition(session, order, S.AWAITING_COMPLETION, ActorType.USER, user.id)
    hours = await settings_svc.get(session, "auto_complete_hours")
    order.delivered_at = now()
    order.auto_complete_at = now() + timedelta(hours=hours)
    notify.queue(
        session,
        order.client_id,
        "order.delivered",
        buttons=[
            [Button("btn.complete", callback=f"o:complete:{order.id}")],
            [view_button(order.id, "btn.problem")],
        ],
        order_id=order.id,
        hours=hours,
    )
    return order


def _check_delivery_code(order: Order, code: str | None) -> None:
    if (order.delivery_code_attempts or 0) >= DELIVERY_CODE_MAX_ATTEMPTS:
        raise DomainError("code_locked")  # resolved through a complaint
    code = (code or "").strip()
    if not code:
        raise DomainError("code_required")
    if secrets.compare_digest(code.encode(), order.delivery_code.encode()):
        return
    order.delivery_code_attempts = (order.delivery_code_attempts or 0) + 1
    left = DELIVERY_CODE_MAX_ATTEMPTS - order.delivery_code_attempts
    # commit=True: the failed attempt is stored even though the action fails
    if left <= 0:
        raise DomainError("code_locked", commit=True)
    raise DomainError("invalid_code", commit=True, attempts_left=left)


async def complete(session: AsyncSession, user: User, order_id: int) -> Order:
    order = await get_for(session, user, order_id)
    if order.client_id != user.id:
        raise forbidden()
    if order.status != S.AWAITING_COMPLETION:  # DISPUTED -> COMPLETED is an admin-only decision
        raise DomainError("invalid_transition")
    _transition(session, order, S.COMPLETED, ActorType.USER, user.id)
    _on_completed(session, order)
    return order


def _on_completed(session: AsyncSession, order: Order) -> None:
    order.completed_at = now()
    order.auto_complete_at = None
    for uid in (order.client_id, order.carrier_id):
        notify.queue(
            session, uid, "order.completed", buttons=[[view_button(order.id, "btn.review")]], order_id=order.id
        )


# ---------------------------------------------------------------- cancellation


async def cancel(session: AsyncSession, user: User, order_id: int, reason_code: str, text: str | None) -> Order:
    order = await get_for(session, user, order_id)
    if reason_code not in CANCEL_REASONS:
        raise DomainError("invalid_input")
    if order.status not in USER_CANCELLABLE:
        raise DomainError("invalid_transition")
    role = "CLIENT" if user.id == order.client_id else "CARRIER"
    await _do_cancel(session, order, role, ActorType.USER, user.id, reason_code, text)
    other = order.carrier_id if role == "CLIENT" else order.client_id
    notify.queue(
        session, other, "order.cancelled", buttons=[[view_button(order.id)]], order_id=order.id, reason=reason_code
    )
    return order


async def _do_cancel(session, order: Order, role: str, actor: ActorType, actor_id, reason_code: str, text=None):
    status_at = order.status
    hours_before = (order.departure_at - now()).total_seconds() / 3600
    _transition(session, order, S.CANCELLED, actor, actor_id, reason=reason_code)
    order.cancelled_at = now()
    session.add(
        Cancellation(
            order_id=order.id,
            initiator_id=actor_id if actor == ActorType.USER else None,
            initiator_role=role,
            reason_code=reason_code,
            reason_text=(text or "").strip()[:1000] or None,
            status_at_cancel=status_at,
            hours_before_departure=round(hours_before, 2),
        )
    )
    await listings_svc.release(session, order.listing_id, order.quantity)
    listing = await session.get(Listing, order.listing_id)
    await session.refresh(listing)
    if listing.kind == ListingKind.REQUEST and listing.status == ListingStatus.CLOSED and listing.departure_at > now():
        listing.status = ListingStatus.PUBLISHED  # the client can pick another carrier
        listing.closed_at = None
    if actor == ActorType.USER:
        user = await session.get(User, actor_id)
        user.cancel_count += 1
        late_hours = await settings_svc.get(session, "late_cancel_hours")
        if status_at == S.CONFIRMED and hours_before < late_hours:
            user.late_cancel_count += 1


# ---------------------------------------------------------------- disputes


async def complain(session: AsyncSession, user: User, order_id: int, reason_code: str, text: str | None) -> Complaint:
    order = await get_for(session, user, order_id)
    if reason_code not in COMPLAINT_REASONS:
        raise DomainError("invalid_input")
    if order.status not in COMPLAINABLE:
        raise DomainError("invalid_transition")
    order.status_before_dispute = order.status
    _transition(session, order, S.DISPUTED, ActorType.USER, user.id, reason=reason_code)
    order.auto_complete_at = None
    complaint = Complaint(order_id=order.id, author_id=user.id, reason_code=reason_code, text=(text or "").strip()[:2000] or None)
    session.add(complaint)
    await session.flush()
    other = order.carrier_id if user.id == order.client_id else order.client_id
    notify.queue(session, other, "order.disputed", buttons=[[view_button(order.id)]], order_id=order.id)
    notify.queue_admin(session, "admin.complaint", order_id=order.id, complaint_id=complaint.id, reason=reason_code)
    return complaint


async def resolve_complaint(session: AsyncSession, complaint_id: int, outcome: str, resolution: str, admin: AdminUser):
    complaint = await session.get(Complaint, complaint_id)
    if complaint is None:
        raise not_found()
    if complaint.status != ComplaintStatus.OPEN:
        raise DomainError("invalid_transition")
    if outcome not in (S.COMPLETED, S.CANCELLED) or not resolution.strip():
        raise DomainError("reason_required")
    order = await get(session, complaint.order_id)
    if order.status != S.DISPUTED:
        raise DomainError("invalid_transition")
    if outcome == S.COMPLETED:
        _transition(session, order, S.COMPLETED, ActorType.ADMIN, admin.id, reason=resolution)
        _on_completed(session, order)
    else:
        await _do_cancel(session, order, "ADMIN", ActorType.ADMIN, admin.id, "ADMIN_DECISION", resolution)
    complaint.status = ComplaintStatus.RESOLVED
    complaint.outcome = outcome
    complaint.resolution = resolution.strip()
    complaint.resolved_by = admin.id
    complaint.resolved_at = now()
    audit.log_admin(session, admin, "complaint.resolve", "complaint", complaint.id, outcome=outcome, resolution=resolution)
    for uid in (order.client_id, order.carrier_id):
        notify.queue(
            session,
            uid,
            "order.dispute_resolved",
            buttons=[[view_button(order.id)]],
            order_id=order.id,
            resolution=resolution.strip(),
        )


# ---------------------------------------------------------------- system jobs


async def timeout_confirmations(session: AsyncSession) -> int:
    q = select(Order).where(Order.status == S.AWAITING_CONFIRMATION, Order.confirm_deadline <= now())
    n = 0
    for order in (await session.execute(q)).scalars().all():
        await _do_cancel(session, order, "SYSTEM", ActorType.SYSTEM, None, "CONFIRM_TIMEOUT")
        for uid in (order.client_id, order.carrier_id):
            notify.queue(session, uid, "order.confirm_timeout", order_id=order.id)
        n += 1
    return n


async def auto_complete(session: AsyncSession) -> int:
    q = select(Order).where(Order.status == S.AWAITING_COMPLETION, Order.auto_complete_at <= now())
    n = 0
    for order in (await session.execute(q)).scalars().all():
        _transition(session, order, S.COMPLETED, ActorType.SYSTEM, None, reason="AUTO_COMPLETE")
        _on_completed(session, order)
        n += 1
    return n


async def send_reminders(session: AsyncSession) -> int:
    minutes = await settings_svc.get(session, "reminder_before_minutes")
    q = select(Order).where(
        Order.status == S.CONFIRMED,
        Order.reminder_sent.is_(False),
        Order.departure_at <= now() + timedelta(minutes=minutes),
    )
    n = 0
    for order in (await session.execute(q)).scalars().all():
        order.reminder_sent = True
        for uid in (order.client_id, order.carrier_id):
            buttons = [[view_button(order.id)]]
            if uid == order.carrier_id:
                buttons.insert(0, [Button("btn.start", callback=f"o:start:{order.id}")])
            notify.queue(session, uid, "order.reminder", buttons=buttons, order_id=order.id)
        n += 1
    return n
