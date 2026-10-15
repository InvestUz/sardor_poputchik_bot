"""JSON views. Privacy rules (TZ §8) live here: exact addresses, phones and plates are only
returned to the people who need them, and only after an order is confirmed."""

from app.enums import REVEALED_STATUSES, ListingKind, OrderStatus
from app.models import Listing, Location, Offer, Order, OrderStatusHistory, Review, User, Vehicle
from app.services import orders as orders_svc

# {user_id: {"trips": int, "verified": bool}} from services.profiles.public_stats (one query per request)
Stats = dict[int, dict] | None


def location(loc: Location | None) -> dict | None:
    if loc is None:
        return None
    return {"id": loc.id, "name_uz": loc.name_uz, "name_ru": loc.name_ru, "region_uz": loc.region_uz, "region_ru": loc.region_ru}


def user_public(u: User, stats: Stats = None) -> dict:
    st = (stats or {}).get(u.id) or {}
    return {
        "id": u.id,
        "name": u.first_name or u.username or f"#{u.id}",
        "rating": u.rating,
        "rating_count": u.rating_count,
        "trips": st.get("trips", 0),
        "verified": st.get("verified", False),
    }


def user_contact(u: User, stats: Stats = None) -> dict:
    return {**user_public(u, stats), "full_name": u.display_name, "phone": u.phone, "username": u.username}


def user_profile(p: dict) -> dict:
    u: User = p["user"]
    return {
        "id": u.id,
        "name": u.first_name or u.username or f"#{u.id}",
        "rating": u.rating,
        "rating_count": u.rating_count,
        "trips": p["stats"]["trips"],
        "verified": p["stats"]["verified"],
        "member_since": u.created_at.isoformat(),
        "checks": p["checks"],
        "reviews": [
            {"rating": r.rating, "text": r.text, "author": r.author.first_name, "created_at": r.created_at.isoformat()}
            for r in p["reviews"]
        ],
    }


def vehicle(v: Vehicle | None, with_plate: bool) -> dict | None:
    if v is None:
        return None
    d = {
        "id": v.id,
        "vehicle_type": v.vehicle_type,
        "make_model": v.make_model,
        "color": v.color,
        "seats": v.seats,
        "max_weight_kg": v.max_weight_kg,
    }
    if with_plate:
        d["plate_number"] = v.plate_number
    return d


def listing(l: Listing, viewer_id: int, pending_offers: int | None = None, stats: Stats = None) -> dict:
    mine = l.author_id == viewer_id
    d = {
        "id": l.id,
        "kind": l.kind,
        "category": l.category,
        "status": l.status,
        "from": location(l.from_location),
        "to": location(l.to_location),
        "departure_at": l.departure_at.isoformat(),
        "time_flexible": l.time_flexible,
        "price": l.price,
        "capacity_total": l.capacity_total,
        "capacity_available": l.capacity_available,
        "details": l.details or {},
        "comment": l.comment,
        "photo_ids": [p.file_id for p in l.photos],
        "author": user_public(l.author, stats),
        "vehicle": vehicle(l.vehicle, with_plate=mine),
        "created_at": l.created_at.isoformat(),
        "is_mine": mine,
    }
    if mine:
        d.update(
            from_address=l.from_address,
            to_address=l.to_address,
            recipient_name=l.recipient_name,
            recipient_phone=l.recipient_phone,
            pending_offers=pending_offers,
        )
    return d


def offer(o: Offer, viewer_id: int, stats: Stats = None) -> dict:
    lst = o.listing
    d = {
        "id": o.id,
        "listing_id": o.listing_id,
        "parent_id": o.parent_id,
        "status": o.status,
        "price": o.price,
        "quantity": o.quantity,
        "details": o.details or {},
        "comment": o.comment,
        "photo_ids": [p.file_id for p in o.photos],
        "counterparty": user_public(o.counterparty, stats),
        "vehicle": vehicle(o.vehicle, with_plate=False),
        "proposed_by_me": o.proposed_by_id == viewer_id,
        "can_respond": o.status == "PENDING" and o.proposed_by_id != viewer_id,
        "expires_at": o.expires_at.isoformat(),
        "created_at": o.created_at.isoformat(),
        "listing_kind": lst.kind,
        "listing_category": lst.category,
        "listing_status": lst.status,
        "route": {
            "from": location(lst.from_location),
            "to": location(lst.to_location),
            "departure_at": lst.departure_at.isoformat(),
        },
    }
    # client's exact addresses on a route booking stay hidden from the carrier until confirmation
    if viewer_id == o.counterparty_id and lst.kind == ListingKind.ROUTE:
        d.update(from_address=o.from_address, to_address=o.to_address,
                 recipient_name=o.recipient_name, recipient_phone=o.recipient_phone)
    return d


def order_actions(o: Order, viewer_id: int, reviewed: bool) -> list[str]:
    S = OrderStatus
    if viewer_id == o.carrier_id:
        table = {
            S.AWAITING_CONFIRMATION: ["confirm", "cancel"],
            S.CONFIRMED: ["start", "cancel", "complain"],
            S.IN_PROGRESS: ["deliver", "complain"],
            S.AWAITING_COMPLETION: ["complain"],
        }
    else:
        table = {
            S.AWAITING_CONFIRMATION: ["cancel"],
            S.CONFIRMED: ["cancel", "complain"],
            S.IN_PROGRESS: ["complain"],
            S.AWAITING_COMPLETION: ["complete", "complain"],
        }
    actions = list(table.get(o.status, []))
    if viewer_id == o.carrier_id and orders_svc.code_attempts_left(o) == 0 and "deliver" in actions:
        actions.remove("deliver")  # code locked: only a complaint can move the order on
    if o.status == S.COMPLETED and not reviewed:
        actions.append("review")
    return actions


def order(
    o: Order,
    viewer_id: int,
    reviews: list[Review] | None = None,
    stats: Stats = None,
    history: list[OrderStatusHistory] | None = None,
) -> dict:
    is_carrier = viewer_id == o.carrier_id
    other = o.client if is_carrier else o.carrier
    revealed = o.status in REVEALED_STATUSES
    my_review = next((r for r in reviews or [] if r.author_id == viewer_id), None)
    d = {
        "id": o.id,
        "listing_id": o.listing_id,
        "role": "carrier" if is_carrier else "client",
        "category": o.category,
        "status": o.status,
        "price": o.price,
        "quantity": o.quantity,
        "from": location(o.from_location),
        "to": location(o.to_location),
        "departure_at": o.departure_at.isoformat(),
        "details": o.details or {},
        "counterparty": user_contact(other, stats) if revealed else user_public(other, stats),
        "vehicle": vehicle(o.vehicle, with_plate=revealed),
        "confirm_deadline": o.confirm_deadline.isoformat() if o.confirm_deadline else None,
        "auto_complete_at": o.auto_complete_at.isoformat() if o.auto_complete_at else None,
        "created_at": o.created_at.isoformat(),
        "my_review": {"rating": my_review.rating, "text": my_review.text} if my_review else None,
        "actions": order_actions(o, viewer_id, my_review is not None),
        "revealed": revealed,
        "timeline": orders_svc.timeline(history or []),
        # parcel handover code: only the client sees it; the carrier only learns whether it is needed
        "delivery_code": (
            o.delivery_code
            if not is_carrier and o.status in orders_svc.DELIVERY_CODE_VISIBLE
            else None
        ),
        "needs_code": is_carrier and orders_svc.needs_delivery_code(o),
        "code_attempts_left": orders_svc.code_attempts_left(o) if is_carrier else None,
        "code_locked": is_carrier and orders_svc.code_attempts_left(o) == 0,
    }
    if revealed:
        d.update(from_address=o.from_address, to_address=o.to_address,
                 recipient_name=o.recipient_name, recipient_phone=o.recipient_phone)
    return d


def order_brief(o: Order, viewer_id: int, stats: Stats = None) -> dict:
    is_carrier = viewer_id == o.carrier_id
    return {
        "id": o.id,
        "role": "carrier" if is_carrier else "client",
        "category": o.category,
        "status": o.status,
        "price": o.price,
        "from": location(o.from_location),
        "to": location(o.to_location),
        "departure_at": o.departure_at.isoformat(),
        "counterparty": user_public(o.client if is_carrier else o.carrier, stats),
    }
