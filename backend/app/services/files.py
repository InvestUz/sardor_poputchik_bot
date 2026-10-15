"""Uploaded photos/documents. Images are re-encoded (strips EXIF/GPS and any embedded payload)."""

import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.enums import FilePurpose
from app.models import Listing, ListingPhoto, Offer, OfferPhoto, Order, StoredFile, User
from app.services.errors import DomainError
from app.timeutil import now

MAX_SIDE = 2000
PDF_MAGIC = b"%PDF-"


def _root() -> Path:
    return Path(settings.files_dir)


def _process(data: bytes, purpose: str) -> tuple[bytes, str, str]:
    if data.startswith(PDF_MAGIC):
        if purpose != FilePurpose.DOCUMENT:
            raise DomainError("invalid_file")
        return data, "application/pdf", "pdf"
    try:
        img = Image.open(io.BytesIO(data))
        img.verify()
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise DomainError("invalid_file")
    if img.format not in {"JPEG", "PNG", "WEBP", "HEIF", "MPO"} and img.format is not None:
        raise DomainError("invalid_file")
    img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)
    return out.getvalue(), "image/jpeg", "jpg"


async def save_upload(session: AsyncSession, owner: User, data: bytes, purpose: str) -> StoredFile:
    if purpose not in FilePurpose.__members__:
        raise DomainError("invalid_input")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise DomainError("file_too_large")
    content, mime, ext = _process(data, purpose)
    rel = Path(now().strftime("%Y/%m")) / f"{uuid.uuid4().hex}.{ext}"
    full = _root() / rel
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(content)
    f = StoredFile(owner_id=owner.id, path=rel.as_posix(), mime=mime, size=len(content), purpose=purpose)
    session.add(f)
    await session.flush()
    return f


def full_path(f: StoredFile) -> Path:
    p = (_root() / f.path).resolve()
    if _root().resolve() not in p.parents:
        raise DomainError("not_found", 404)
    return p


async def owned_files(session: AsyncSession, owner: User, ids: list[int], purpose: str) -> list[StoredFile]:
    if not ids:
        return []
    files = (
        await session.execute(select(StoredFile).where(StoredFile.id.in_(ids), StoredFile.owner_id == owner.id))
    ).scalars().all()
    if len(files) != len(set(ids)) or any(f.purpose != purpose for f in files):
        raise DomainError("invalid_file")
    return list(files)


async def can_access(session: AsyncSession, user: User, f: StoredFile) -> bool:
    if f.owner_id == user.id:
        return True
    if f.purpose == FilePurpose.LISTING_PHOTO:
        return (
            await session.execute(select(ListingPhoto.id).where(ListingPhoto.file_id == f.id))
        ).first() is not None
    if f.purpose == FilePurpose.OFFER_PHOTO:
        row = (
            await session.execute(
                select(Offer.counterparty_id, Listing.author_id)
                .join(OfferPhoto, OfferPhoto.offer_id == Offer.id)
                .join(Listing, Listing.id == Offer.listing_id)
                .where(OfferPhoto.file_id == f.id)
            )
        ).first()
        if row and user.id in (row[0], row[1]):
            return True
        # the carrier of the resulting order may also see it
        order = (
            await session.execute(
                select(Order.id)
                .join(OfferPhoto, OfferPhoto.offer_id == Order.offer_id)
                .where(OfferPhoto.file_id == f.id, (Order.client_id == user.id) | (Order.carrier_id == user.id))
            )
        ).first()
        return order is not None
    return False  # documents: owner and admins only
