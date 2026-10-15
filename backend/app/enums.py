from enum import StrEnum


class Lang(StrEnum):
    UZ = "uz"
    RU = "ru"


class Category(StrEnum):
    PASSENGER = "PASSENGER"
    DOCUMENTS = "DOCUMENTS"
    PARCEL = "PARCEL"
    FURNITURE = "FURNITURE"
    CARGO = "CARGO"


class ListingKind(StrEnum):
    REQUEST = "REQUEST"  # created by a client: "I need a ride / delivery"
    ROUTE = "ROUTE"  # created by a carrier: "I am driving A -> B, N seats / kg free"


class ListingStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class OfferStatus(StrEnum):
    PENDING = "PENDING"
    COUNTERED = "COUNTERED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
    AUTO_CLOSED = "AUTO_CLOSED"


class OrderStatus(StrEnum):
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    AWAITING_COMPLETION = "AWAITING_COMPLETION"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    DISPUTED = "DISPUTED"


# Statuses in which both sides see exact addresses and contacts.
REVEALED_STATUSES = {
    OrderStatus.CONFIRMED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.AWAITING_COMPLETION,
    OrderStatus.COMPLETED,
    OrderStatus.DISPUTED,
}

ACTIVE_ORDER_STATUSES = {
    OrderStatus.AWAITING_CONFIRMATION,
    OrderStatus.CONFIRMED,
    OrderStatus.IN_PROGRESS,
    OrderStatus.AWAITING_COMPLETION,
    OrderStatus.DISPUTED,
}


class CarrierStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RESUBMIT = "RESUBMIT"
    REVOKED = "REVOKED"


class DocumentKind(StrEnum):
    DRIVER_LICENSE = "DRIVER_LICENSE"
    TECH_PASSPORT = "TECH_PASSPORT"
    VEHICLE_PHOTO = "VEHICLE_PHOTO"
    ID_CARD = "ID_CARD"
    OTHER = "OTHER"


class VehicleType(StrEnum):
    SEDAN = "SEDAN"
    MINIVAN = "MINIVAN"
    MINIBUS = "MINIBUS"
    VAN = "VAN"
    TRUCK_SMALL = "TRUCK_SMALL"
    TRUCK = "TRUCK"


class ComplaintStatus(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class AdminRole(StrEnum):
    SUPERADMIN = "SUPERADMIN"
    MODERATOR = "MODERATOR"
    SUPPORT = "SUPPORT"


class ActorType(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"
    SYSTEM = "SYSTEM"


class FilePurpose(StrEnum):
    DOCUMENT = "DOCUMENT"
    LISTING_PHOTO = "LISTING_PHOTO"
    OFFER_PHOTO = "OFFER_PHOTO"


CANCEL_REASONS = ["PLANS_CHANGED", "FOUND_OTHER", "PARTY_NO_RESPONSE", "PRICE", "VEHICLE_ISSUE", "OTHER"]
COMPLAINT_REASONS = ["NO_SHOW", "LATE", "NOT_AS_DESCRIBED", "DAMAGE_OR_LOSS", "PRICE_DISPUTE", "RUDE", "OTHER"]
