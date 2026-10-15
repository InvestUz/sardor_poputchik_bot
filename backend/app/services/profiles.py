"""Public trust data about a user: completed trips, verification, document checks, latest reviews."""

from sqlalchemy import func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CarrierStatus, DocumentKind, OrderStatus
from app.models import CarrierProfile, Document, Order, User
from app.services import reviews
from app.services.errors import not_found

CHECK_DOCUMENTS = {
    "driver_license": DocumentKind.DRIVER_LICENSE,
    "tech_passport": DocumentKind.TECH_PASSPORT,
    "vehicle_photo": DocumentKind.VEHICLE_PHOTO,
}


async def public_stats(session: AsyncSession, user_ids) -> dict[int, dict]:
    """{user_id: {"trips": int, "verified": bool}} for many users in two queries (no N+1).

    trips = COMPLETED orders; a verified carrier counts only orders served as the carrier."""
    ids = {i for i in user_ids if i is not None}
    if not ids:
        return {}
    verified = set(
        (
            await session.execute(
                select(CarrierProfile.user_id).where(
                    CarrierProfile.user_id.in_(ids), CarrierProfile.status == CarrierStatus.APPROVED
                )
            )
        ).scalars()
    )
    done = Order.status == OrderStatus.COMPLETED
    parts = union_all(
        select(Order.carrier_id.label("uid"), Order.id.label("oid"), literal(1).label("as_carrier"))
        .where(done, Order.carrier_id.in_(ids)),
        select(Order.client_id.label("uid"), Order.id.label("oid"), literal(0).label("as_carrier"))
        .where(done, Order.client_id.in_(ids)),
    ).subquery()
    rows = await session.execute(
        select(parts.c.uid, parts.c.as_carrier, func.count(parts.c.oid)).group_by(parts.c.uid, parts.c.as_carrier)
    )
    as_carrier: dict[int, int] = {}
    as_any: dict[int, int] = {}
    for uid, carrier_flag, n in rows:
        as_any[uid] = as_any.get(uid, 0) + n
        if carrier_flag:
            as_carrier[uid] = as_carrier.get(uid, 0) + n
    return {
        uid: {
            "trips": as_carrier.get(uid, 0) if uid in verified else as_any.get(uid, 0),
            "verified": uid in verified,
        }
        for uid in ids
    }


async def profile(session: AsyncSession, user_id: int) -> dict:
    user = await session.get(User, user_id)
    if user is None:
        raise not_found()
    stats = (await public_stats(session, [user.id]))[user.id]
    kinds: set[str] = set()
    if stats["verified"]:
        kinds = set((await session.execute(select(Document.kind).where(Document.user_id == user.id))).scalars())
    return {
        "user": user,
        "stats": stats,
        "checks": {
            "phone": bool(user.phone),
            **{name: kind.value in kinds for name, kind in CHECK_DOCUMENTS.items()},
        },
        "reviews": await reviews.about_user(session, user.id, limit=3),
    }
