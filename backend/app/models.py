from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime
from app.enums import (
    CarrierStatus,
    ComplaintStatus,
    ListingStatus,
    OfferStatus,
)
from app.timeutil import now


def _ts(**kw) -> Any:
    return mapped_column(UTCDateTime, **kw)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    last_name: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    lang: Mapped[str] = mapped_column(String(2), default="uz")
    terms_version: Mapped[str | None] = mapped_column(String(16))
    terms_accepted_at: Mapped[datetime | None] = _ts(nullable=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[str | None] = mapped_column(Text)
    bot_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    rating_sum: Mapped[int] = mapped_column(Integer, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    cancel_count: Mapped[int] = mapped_column(Integer, default=0)
    late_cancel_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _ts(default=now)

    carrier_profile: Mapped["CarrierProfile | None"] = relationship(back_populates="user", uselist=False)

    @property
    def is_registered(self) -> bool:
        return bool(self.phone) and self.terms_accepted_at is not None

    @property
    def rating(self) -> float | None:
        return round(self.rating_sum / self.rating_count, 2) if self.rating_count else None

    @property
    def display_name(self) -> str:
        return " ".join(p for p in [self.first_name, self.last_name] if p) or (self.username or f"#{self.id}")


class CarrierProfile(Base):
    __tablename__ = "carrier_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    status: Mapped[str] = mapped_column(String(16), default=CarrierStatus.DRAFT)
    full_name: Mapped[str | None] = mapped_column(String(256))
    admin_comment: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = _ts(nullable=True)
    reviewed_at: Mapped[datetime | None] = _ts(nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    created_at: Mapped[datetime] = _ts(default=now)

    user: Mapped[User] = relationship(back_populates="carrier_profile")


class CarrierPermission(Base):
    __tablename__ = "carrier_permissions"
    __table_args__ = (UniqueConstraint("user_id", "category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category: Mapped[str] = mapped_column(String(16))
    granted_at: Mapped[datetime] = _ts(default=now)
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vehicle_type: Mapped[str] = mapped_column(String(16))
    make_model: Mapped[str] = mapped_column(String(128))
    plate_number: Mapped[str] = mapped_column(String(16))
    color: Mapped[str | None] = mapped_column(String(32))
    seats: Mapped[int] = mapped_column(Integer, default=0)
    max_weight_kg: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts(default=now)


class StoredFile(Base):
    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    path: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = _ts(default=now)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id"))
    created_at: Mapped[datetime] = _ts(default=now)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    region_uz: Mapped[str] = mapped_column(String(64))
    region_ru: Mapped[str] = mapped_column(String(64))
    name_uz: Mapped[str] = mapped_column(String(64))
    name_ru: Mapped[str] = mapped_column(String(64))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    sort: Mapped[int] = mapped_column(Integer, default=0)

    def name(self, lang: str) -> str:
        return self.name_ru if lang == "ru" else self.name_uz


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("capacity_reserved >= 0 AND capacity_reserved <= capacity_total", name="capacity"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))
    category: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default=ListingStatus.PUBLISHED, index=True)
    from_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    to_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    departure_at: Mapped[datetime] = _ts(index=True)
    time_flexible: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[int] = mapped_column(BigInteger)
    # REQUEST: always 1 (one executor). ROUTE: seats (PASSENGER) or kg (PARCEL).
    capacity_total: Mapped[int] = mapped_column(Integer, default=1)
    capacity_reserved: Mapped[int] = mapped_column(Integer, default=0)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    details: Mapped[dict] = mapped_column(JSON, default=dict)  # public, category-specific
    comment: Mapped[str | None] = mapped_column(Text)
    # Hidden until an order is confirmed:
    from_address: Mapped[str | None] = mapped_column(Text)
    to_address: Mapped[str | None] = mapped_column(Text)
    recipient_name: Mapped[str | None] = mapped_column(String(128))
    recipient_phone: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = _ts(default=now)
    closed_at: Mapped[datetime | None] = _ts(nullable=True)

    author: Mapped[User] = relationship(foreign_keys=[author_id])
    vehicle: Mapped[Vehicle | None] = relationship()
    from_location: Mapped[Location] = relationship(foreign_keys=[from_location_id])
    to_location: Mapped[Location] = relationship(foreign_keys=[to_location_id])
    photos: Mapped[list["ListingPhoto"]] = relationship(order_by="ListingPhoto.id")

    @property
    def capacity_available(self) -> int:
        return self.capacity_total - self.capacity_reserved


class ListingPhoto(Base):
    __tablename__ = "listing_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id"))


class ListingView(Base):
    """A unique non-author user who opened a listing (author's live activity counter)."""

    __tablename__ = "listing_views"
    __table_args__ = (UniqueConstraint("listing_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = _ts(default=now)


class Offer(Base):
    """One negotiation step. A counter-offer creates a new row with parent_id."""

    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    counterparty_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)  # the non-author side
    proposed_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id"))
    price: Mapped[int] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    comment: Mapped[str | None] = mapped_column(Text)
    from_address: Mapped[str | None] = mapped_column(Text)
    to_address: Mapped[str | None] = mapped_column(Text)
    recipient_name: Mapped[str | None] = mapped_column(String(128))
    recipient_phone: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default=OfferStatus.PENDING, index=True)
    expires_at: Mapped[datetime] = _ts()
    created_at: Mapped[datetime] = _ts(default=now)
    decided_at: Mapped[datetime | None] = _ts(nullable=True)

    listing: Mapped[Listing] = relationship()
    counterparty: Mapped[User] = relationship(foreign_keys=[counterparty_id])
    vehicle: Mapped[Vehicle | None] = relationship()
    photos: Mapped[list["OfferPhoto"]] = relationship(order_by="OfferPhoto.id")


class OfferPhoto(Base):
    __tablename__ = "offer_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("stored_files.id"))


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id"), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    carrier_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    category: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), index=True)
    status_before_dispute: Mapped[str | None] = mapped_column(String(24))
    price: Mapped[int] = mapped_column(BigInteger)
    quantity: Mapped[int] = mapped_column(Integer)
    # Fixed at creation so later setting changes do not affect this order.
    commission_percent: Mapped[float] = mapped_column(Float)
    estimated_commission: Mapped[int] = mapped_column(BigInteger)
    from_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    to_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    departure_at: Mapped[datetime] = _ts()
    from_address: Mapped[str | None] = mapped_column(Text)
    to_address: Mapped[str | None] = mapped_column(Text)
    recipient_name: Mapped[str | None] = mapped_column(String(128))
    recipient_phone: Mapped[str | None] = mapped_column(String(32))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    # Parcel handover code (non-passenger orders): told by the client to the recipient, entered by the carrier.
    delivery_code: Mapped[str | None] = mapped_column(String(8))
    delivery_code_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    confirm_deadline: Mapped[datetime | None] = _ts(nullable=True)
    auto_complete_at: Mapped[datetime | None] = _ts(nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _ts(default=now)
    confirmed_at: Mapped[datetime | None] = _ts(nullable=True)
    started_at: Mapped[datetime | None] = _ts(nullable=True)
    delivered_at: Mapped[datetime | None] = _ts(nullable=True)
    completed_at: Mapped[datetime | None] = _ts(nullable=True)
    cancelled_at: Mapped[datetime | None] = _ts(nullable=True)

    listing: Mapped[Listing] = relationship()
    client: Mapped[User] = relationship(foreign_keys=[client_id])
    carrier: Mapped[User] = relationship(foreign_keys=[carrier_id])
    vehicle: Mapped[Vehicle | None] = relationship()
    from_location: Mapped[Location] = relationship(foreign_keys=[from_location_id])
    to_location: Mapped[Location] = relationship(foreign_keys=[to_location_id])


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    actor_type: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[int | None] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts(default=now)


class Cancellation(Base):
    __tablename__ = "cancellations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    initiator_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    initiator_role: Mapped[str] = mapped_column(String(8))  # CLIENT | CARRIER | SYSTEM | ADMIN
    reason_code: Mapped[str] = mapped_column(String(32))
    reason_text: Mapped[str | None] = mapped_column(Text)
    status_at_cancel: Mapped[str] = mapped_column(String(24))
    hours_before_departure: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = _ts(default=now)


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason_code: Mapped[str] = mapped_column(String(32))
    text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=ComplaintStatus.OPEN, index=True)
    resolution: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(String(24))
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))
    resolved_at: Mapped[datetime | None] = _ts(nullable=True)
    created_at: Mapped[datetime] = _ts(default=now)

    order: Mapped[Order] = relationship()
    author: Mapped[User] = relationship()


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("order_id", "author_id"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="rating_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    target_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _ts(default=now)

    author: Mapped[User] = relationship(foreign_keys=[author_id])
    target: Mapped[User] = relationship(foreign_keys=[target_id])


class Subscription(Base):
    """'Notify me about new listings on this route'."""

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", "kind", "category", "from_location_id", "to_location_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))  # kind of listings to be notified about
    category: Mapped[str] = mapped_column(String(16))
    from_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    to_location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"))
    created_at: Mapped[datetime] = _ts(default=now)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)
    updated_at: Mapped[datetime] = _ts(default=now)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("admin_users.id"))


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _ts(default=now)
    last_login_at: Mapped[datetime | None] = _ts(nullable=True)


class AuditLog(Base):
    """Append-only journal of critical and admin actions."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_type: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[int | None] = mapped_column(Integer)
    actor_name: Mapped[str | None] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = _ts(default=now, index=True)
