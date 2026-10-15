"""Price hint for listing / offer forms: route history first, distance tariff as a fallback."""

import math
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Category, ListingKind, ListingStatus
from app.models import Listing, Location
from app.services import settings as settings_svc
from app.services.errors import DomainError
from app.timeutil import now

HISTORY_DAYS = 90
HISTORY_MIN_LISTINGS = 5
ROAD_FACTOR = 1.25  # straight line -> road distance
SPREAD_LOW, SPREAD_HIGH = 0.85, 1.15
ROUND_TO = 5_000
MAX_SEATS = 8


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def round_price(v: float) -> int:
    return max(ROUND_TO, int(round(v / ROUND_TO)) * ROUND_TO)


def _percentile(values: list[float], q: float) -> float:
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def _unit_price(listing: Listing) -> float:
    """Price for one seat (PASSENGER) or one parcel: a passenger request's price covers all its passengers."""
    if listing.category == Category.PASSENGER and listing.kind == ListingKind.REQUEST:
        return listing.price / max(1, int((listing.details or {}).get("passengers") or 1))
    return float(listing.price)


async def hint(session: AsyncSession, category: str, from_id: int, to_id: int, seats: int = 1) -> dict:
    if category not in Category.__members__:
        raise DomainError("invalid_input")
    if from_id == to_id:
        raise DomainError("same_locations")
    if not 1 <= seats <= MAX_SEATS:
        raise DomainError("invalid_input")
    a, b = await session.get(Location, from_id), await session.get(Location, to_id)
    if a is None or b is None:
        raise DomainError("invalid_input")
    multiplier = seats if category == Category.PASSENGER else 1
    road_km = haversine_km(a.lat, a.lon, b.lat, b.lon) * ROAD_FACTOR

    q = select(Listing).where(
        Listing.category == category,
        Listing.from_location_id == from_id,
        Listing.to_location_id == to_id,
        Listing.status != ListingStatus.DRAFT,
        Listing.created_at >= now() - timedelta(days=HISTORY_DAYS),
    )
    history = [_unit_price(l) for l in (await session.execute(q)).scalars()]
    if len(history) >= HISTORY_MIN_LISTINGS:
        low, typical, high = (_percentile(history, x) * multiplier for x in (0.25, 0.5, 0.75))
        source = "history"
    else:
        key = "price_per_km_passenger" if category == Category.PASSENGER else "price_per_km_parcel"
        typical = road_km * await settings_svc.get(session, key) * multiplier
        low, high = typical * SPREAD_LOW, typical * SPREAD_HIGH
        source = "distance"
    return {
        "min": round_price(low),
        "max": round_price(high),
        "typical": round_price(typical),
        "distance_km": round(road_km),
        "source": source,
    }
