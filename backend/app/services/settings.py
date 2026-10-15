"""Business parameters editable from the admin panel (TZ §17.3). Code never hardcodes them."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Category, DocumentKind
from app.models import AdminUser, Setting
from app.services import audit
from app.services.errors import DomainError
from app.timeutil import now

DEFAULTS: dict[str, Any] = {
    "commission_percent": 10.0,  # pilot: only computed for statistics, never charged
    "offer_ttl_minutes": 120,
    "confirm_timeout_minutes": 30,
    "auto_complete_hours": 12,
    "reminder_before_minutes": 120,
    "late_cancel_hours": 2,
    "enabled_categories": [Category.PASSENGER.value, Category.PARCEL.value],
    "required_documents": [
        DocumentKind.DRIVER_LICENSE.value,
        DocumentKind.TECH_PASSPORT.value,
        DocumentKind.VEHICLE_PHOTO.value,
    ],
    "max_active_listings": 10,
    "max_subscriptions": 10,
    "terms_version": "1",
    "support_contact": "@support",
    # price hint by distance (so'm per road km) when the route has too little history
    "price_per_km_passenger": 550,
    "price_per_km_parcel": 250,
}

# key -> validator returning the normalized value
_VALIDATORS = {
    "commission_percent": lambda v: _num(v, 0, 50, float),
    "offer_ttl_minutes": lambda v: _num(v, 5, 7 * 24 * 60, int),
    "confirm_timeout_minutes": lambda v: _num(v, 5, 24 * 60, int),
    "auto_complete_hours": lambda v: _num(v, 1, 14 * 24, int),
    "reminder_before_minutes": lambda v: _num(v, 10, 24 * 60, int),
    "late_cancel_hours": lambda v: _num(v, 0, 72, float),
    "enabled_categories": lambda v: _subset(v, [c.value for c in Category]),
    "required_documents": lambda v: _subset(v, [d.value for d in DocumentKind]),
    "max_active_listings": lambda v: _num(v, 1, 1000, int),
    "max_subscriptions": lambda v: _num(v, 0, 100, int),
    "terms_version": lambda v: _str(v, 16),
    "support_contact": lambda v: _str(v, 128),
    "price_per_km_passenger": lambda v: _num(v, 1, 100_000, int),
    "price_per_km_parcel": lambda v: _num(v, 1, 100_000, int),
}


def _num(v, lo, hi, typ):
    try:
        v = typ(v)
    except (TypeError, ValueError):
        raise DomainError("invalid_input")
    if not lo <= v <= hi:
        raise DomainError("invalid_input")
    return v


def _subset(v, allowed):
    if isinstance(v, str):
        v = [x.strip() for x in v.split(",") if x.strip()]
    if not isinstance(v, list) or any(x not in allowed for x in v):
        raise DomainError("invalid_input")
    return v


def _str(v, max_len):
    v = str(v).strip()
    if not v or len(v) > max_len:
        raise DomainError("invalid_input")
    return v


async def get_all(session: AsyncSession) -> dict[str, Any]:
    values = dict(DEFAULTS)
    for row in (await session.execute(select(Setting))).scalars():
        if row.key in values:
            values[row.key] = row.value
    return values


async def get(session: AsyncSession, key: str) -> Any:
    row = await session.get(Setting, key)
    return row.value if row is not None else DEFAULTS[key]


async def set_value(session: AsyncSession, key: str, value: Any, admin: AdminUser) -> None:
    if key not in _VALIDATORS:
        raise DomainError("invalid_input")
    value = _VALIDATORS[key](value)
    row = await session.get(Setting, key)
    old = row.value if row else DEFAULTS[key]
    if old == value:
        return
    if row is None:
        session.add(Setting(key=key, value=value, updated_by=admin.id, updated_at=now()))
    else:
        row.value, row.updated_by, row.updated_at = value, admin.id, now()
    audit.log_admin(session, admin, "setting.update", "setting", None, key=key, old=old, new=value)
