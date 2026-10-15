"""Admin dashboard statistics (TZ §17.4)."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CarrierStatus, ComplaintStatus, ListingStatus, OrderStatus
from app.models import CarrierProfile, Complaint, Listing, Location, Offer, Order, User


async def dashboard(session: AsyncSession) -> dict:
    async def count(model, *where):
        return await session.scalar(select(func.count()).select_from(model).where(*where))

    completed = Order.status == OrderStatus.COMPLETED
    by_status = dict((await session.execute(select(Order.status, func.count()).group_by(Order.status))).all())
    by_category = (
        await session.execute(
            select(Order.category, func.count(), func.coalesce(func.sum(Order.price), 0)).where(completed).group_by(Order.category)
        )
    ).all()
    top_routes = (
        await session.execute(
            select(Listing.from_location_id, Listing.to_location_id, func.count().label("n"))
            .group_by(Listing.from_location_id, Listing.to_location_id)
            .order_by(func.count().desc())
            .limit(10)
        )
    ).all()
    loc_names = dict((await session.execute(select(Location.id, Location.name_uz))).all())

    return {
        "users": await count(User),
        "users_registered": await count(User, User.terms_accepted_at.is_not(None)),
        "carriers_approved": await count(CarrierProfile, CarrierProfile.status == CarrierStatus.APPROVED),
        "carriers_pending": await count(CarrierProfile, CarrierProfile.status == CarrierStatus.PENDING),
        "listings_active": await count(Listing, Listing.status == ListingStatus.PUBLISHED),
        "listings_total": await count(Listing),
        "offers_total": await count(Offer),
        "orders_by_status": by_status,
        "orders_total": sum(by_status.values()),
        "complaints_open": await count(Complaint, Complaint.status == ComplaintStatus.OPEN),
        "gmv_completed": await session.scalar(select(func.coalesce(func.sum(Order.price), 0)).where(completed)),
        "commission_estimated": await session.scalar(
            select(func.coalesce(func.sum(Order.estimated_commission), 0)).where(completed)
        ),
        "by_category": [{"category": c, "orders": n, "gmv": s} for c, n, s in by_category],
        "top_routes": [
            {"route": f"{loc_names.get(a, a)} → {loc_names.get(b, b)}", "listings": n} for a, b, n in top_routes
        ],
    }
