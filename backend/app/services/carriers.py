"""Carrier verification (TZ §3, §5.7, §17.1)."""

import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import CarrierStatus, Category, DocumentKind, FilePurpose, VehicleType
from app.models import AdminUser, CarrierPermission, CarrierProfile, Document, User, Vehicle
from app.services import audit, notify
from app.services import files as files_svc
from app.services import settings as settings_svc
from app.services.errors import DomainError, not_found
from app.services.notify import Button
from app.timeutil import now

EDITABLE = {CarrierStatus.DRAFT, CarrierStatus.REJECTED, CarrierStatus.RESUBMIT, CarrierStatus.REVOKED}


async def get_or_create_profile(session: AsyncSession, user: User) -> CarrierProfile:
    profile = (
        await session.execute(select(CarrierProfile).where(CarrierProfile.user_id == user.id))
    ).scalar_one_or_none()
    if profile is None:
        profile = CarrierProfile(user_id=user.id, status=CarrierStatus.DRAFT)
        session.add(profile)
        await session.flush()
    return profile


async def permissions(session: AsyncSession, user_id: int) -> list[str]:
    rows = await session.execute(select(CarrierPermission.category).where(CarrierPermission.user_id == user_id))
    return [r[0] for r in rows]


async def has_permission(session: AsyncSession, user: User, category: str) -> bool:
    profile = (
        await session.execute(select(CarrierProfile.status).where(CarrierProfile.user_id == user.id))
    ).scalar_one_or_none()
    return profile == CarrierStatus.APPROVED and category in await permissions(session, user.id)


async def vehicles(session: AsyncSession, user: User) -> list[Vehicle]:
    q = select(Vehicle).where(Vehicle.user_id == user.id, Vehicle.is_active.is_(True)).order_by(Vehicle.id)
    return list((await session.execute(q)).scalars())


PLATE_REGIONS = {"01", "10", "20", "25", "30", "40", "50", "60", "70", "75", "80", "85", "90", "95"}
# individual: 01 A 123 BC ; legal entity: 01 123 ABC (stored without spaces)
PLATE_RE = re.compile(r"^(\d{2})(?:[A-Z]\d{3}[A-Z]{2}|\d{3}[A-Z]{3})$")


def normalize_plate(raw: str) -> str:
    plate = re.sub(r"[\s|\-]", "", (raw or "").upper())
    m = PLATE_RE.match(plate)
    if not m or m.group(1) not in PLATE_REGIONS:
        raise DomainError("invalid_plate")
    return plate


def _validate_vehicle(data: dict) -> dict:
    if data.get("vehicle_type") not in VehicleType.__members__:
        raise DomainError("invalid_vehicle")
    make_model = (data.get("make_model") or "").strip()
    plate = normalize_plate(data.get("plate_number") or "")
    seats = int(data.get("seats") or 0)
    weight = int(data.get("max_weight_kg") or 0)
    if not make_model or not 0 <= seats <= 60 or not 0 <= weight <= 40000:
        raise DomainError("invalid_vehicle")
    if seats == 0 and weight == 0:
        raise DomainError("invalid_vehicle")
    return {
        "vehicle_type": data["vehicle_type"],
        "make_model": make_model[:128],
        "plate_number": plate,
        "color": (data.get("color") or "").strip()[:32] or None,
        "seats": seats,
        "max_weight_kg": weight,
    }


async def add_vehicle(session: AsyncSession, user: User, data: dict) -> Vehicle:
    v = Vehicle(user_id=user.id, **_validate_vehicle(data))
    session.add(v)
    await session.flush()
    return v


async def remove_vehicle(session: AsyncSession, user: User, vehicle_id: int) -> None:
    v = await session.get(Vehicle, vehicle_id)
    if v is None or v.user_id != user.id:
        raise not_found()
    v.is_active = False


async def documents(session: AsyncSession, user_id: int) -> list[Document]:
    q = select(Document).where(Document.user_id == user_id).order_by(Document.id)
    return list((await session.execute(q)).scalars())


async def add_document(session: AsyncSession, user: User, kind: str, file_id: int) -> Document:
    if kind not in DocumentKind.__members__:
        raise DomainError("invalid_input")
    profile = await get_or_create_profile(session, user)
    if profile.status not in EDITABLE:
        raise DomainError("already_submitted")
    await files_svc.owned_files(session, user, [file_id], FilePurpose.DOCUMENT)
    doc = Document(user_id=user.id, kind=kind, file_id=file_id)
    session.add(doc)
    await session.flush()
    return doc


async def remove_document(session: AsyncSession, user: User, doc_id: int) -> None:
    profile = await get_or_create_profile(session, user)
    if profile.status not in EDITABLE:
        raise DomainError("already_submitted")
    doc = await session.get(Document, doc_id)
    if doc is None or doc.user_id != user.id:
        raise not_found()
    await session.delete(doc)


async def submit(session: AsyncSession, user: User, full_name: str) -> CarrierProfile:
    profile = await get_or_create_profile(session, user)
    if profile.status not in EDITABLE:
        raise DomainError("already_submitted")
    full_name = (full_name or "").strip()
    if len(full_name) < 3:
        raise DomainError("invalid_input")
    required = set(await settings_svc.get(session, "required_documents"))
    present = {d.kind for d in await documents(session, user.id)}
    if missing := required - present:
        raise DomainError("documents_missing", missing=sorted(missing))
    if not await vehicles(session, user):
        raise DomainError("vehicle_required")
    profile.full_name = full_name[:256]
    profile.status = CarrierStatus.PENDING
    profile.submitted_at = now()
    profile.admin_comment = None
    notify.queue_admin(session, "admin.verification_submitted", name=full_name, user_id=user.id)
    return profile


async def _review(session, profile_id: int, admin: AdminUser, allowed_from: set[str]) -> CarrierProfile:
    profile = await session.get(CarrierProfile, profile_id)
    if profile is None:
        raise not_found()
    if profile.status not in allowed_from:
        raise DomainError("invalid_transition")
    profile.reviewed_at = now()
    profile.reviewed_by = admin.id
    return profile


async def approve(session: AsyncSession, profile_id: int, categories: list[str], admin: AdminUser) -> None:
    if not categories or any(c not in Category.__members__ for c in categories):
        raise DomainError("categories_required")
    profile = await _review(session, profile_id, admin, {CarrierStatus.PENDING, CarrierStatus.APPROVED})
    profile.status = CarrierStatus.APPROVED
    profile.admin_comment = None
    await session.execute(delete(CarrierPermission).where(CarrierPermission.user_id == profile.user_id))
    for c in sorted(set(categories)):
        session.add(CarrierPermission(user_id=profile.user_id, category=c, granted_by=admin.id))
    audit.log_admin(session, admin, "carrier.approve", "carrier_profile", profile.id, categories=categories)
    notify.queue(
        session,
        profile.user_id,
        "carrier.approved",
        buttons=[[Button("btn.open_app", webapp_path="/")]],
        categories=categories,
    )


async def reject(session: AsyncSession, profile_id: int, reason: str, admin: AdminUser, resubmit: bool) -> None:
    if not reason.strip():
        raise DomainError("reason_required")
    profile = await _review(session, profile_id, admin, {CarrierStatus.PENDING})
    profile.status = CarrierStatus.RESUBMIT if resubmit else CarrierStatus.REJECTED
    profile.admin_comment = reason.strip()
    action = "carrier.resubmit" if resubmit else "carrier.reject"
    audit.log_admin(session, admin, action, "carrier_profile", profile.id, reason=reason)
    notify.queue(
        session,
        profile.user_id,
        "carrier.resubmit_requested" if resubmit else "carrier.rejected",
        buttons=[[Button("btn.open_profile", webapp_path="/profile")]],
        reason=reason.strip(),
    )


async def revoke(session: AsyncSession, profile_id: int, reason: str, admin: AdminUser) -> None:
    if not reason.strip():
        raise DomainError("reason_required")
    profile = await _review(session, profile_id, admin, {CarrierStatus.APPROVED})
    profile.status = CarrierStatus.REVOKED
    profile.admin_comment = reason.strip()
    await session.execute(delete(CarrierPermission).where(CarrierPermission.user_id == profile.user_id))
    audit.log_admin(session, admin, "carrier.revoke", "carrier_profile", profile.id, reason=reason)
    notify.queue(session, profile.user_id, "carrier.revoked", reason=reason.strip())
