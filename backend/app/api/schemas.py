from datetime import datetime

from pydantic import BaseModel, Field


class _In(BaseModel):
    model_config = {"extra": "ignore"}


class MeIn(_In):
    lang: str


class ListingIn(_In):
    kind: str
    category: str
    from_location_id: int | None = None
    to_location_id: int | None = None
    departure_at: datetime | None = None
    time_flexible: bool = False
    price: int | None = None
    comment: str | None = None
    vehicle_id: int | None = None
    seats: int | None = None
    capacity_kg: int | None = None
    passengers: int | None = None
    luggage: str | None = None
    stops_allowed: bool = False
    whole_car: bool = False
    description: str | None = None
    quantity: int | None = None
    weight_kg: int | None = None
    length_cm: int | None = None
    width_cm: int | None = None
    height_cm: int | None = None
    fragile: bool = False
    loaders_needed: bool = False
    photo_ids: list[int] = Field(default_factory=list)
    from_address: str | None = None
    to_address: str | None = None
    recipient_name: str | None = None
    recipient_phone: str | None = None


class OfferIn(_In):
    price: int | None = None
    comment: str | None = None
    vehicle_id: int | None = None
    passengers: int | None = None
    luggage: str | None = None
    stops_allowed: bool = False
    whole_car: bool = False
    description: str | None = None
    quantity: int | None = None
    weight_kg: int | None = None
    length_cm: int | None = None
    width_cm: int | None = None
    height_cm: int | None = None
    fragile: bool = False
    photo_ids: list[int] = Field(default_factory=list)
    from_address: str | None = None
    to_address: str | None = None
    recipient_name: str | None = None
    recipient_phone: str | None = None


class CounterIn(_In):
    price: int
    comment: str | None = None


class DeliverIn(_In):
    code: str | None = None


class ReasonIn(_In):
    reason_code: str
    text: str | None = None


class ReviewIn(_In):
    rating: int
    text: str | None = None


class VehicleIn(_In):
    vehicle_type: str
    make_model: str
    plate_number: str
    color: str | None = None
    seats: int = 0
    max_weight_kg: int = 0


class DocumentIn(_In):
    kind: str
    file_id: int


class SubmitIn(_In):
    full_name: str


class SubscriptionIn(_In):
    kind: str
    category: str
    from_location_id: int
    to_location_id: int
