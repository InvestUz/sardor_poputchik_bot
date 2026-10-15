import io
import itertools
from datetime import datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy import select

from app import db
from app.config import settings
from app.db import Base, uow
from app.enums import AdminRole, CarrierStatus
from app.models import AdminUser, CarrierPermission, CarrierProfile, Location, User, Vehicle
from app.services import locations, notify
from app.timeutil import now

_tg_ids = itertools.count(10_000)


class FakeNotifier:
    def __init__(self):
        self.messages: list[notify.Message] = []

    async def deliver(self, messages):
        self.messages.extend(messages)

    def keys(self, user_id: int) -> list[str]:
        return [m.key for m in self.messages if m.user_id == user_id]

    def clear(self):
        self.messages.clear()


@pytest.fixture(autouse=True)
async def database(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "files_dir", str(tmp_path / "files"))
    engine = db.init_engine(f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with uow() as s:
        await locations.seed_if_empty(s)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
def notifier():
    n = FakeNotifier()
    notify.set_notifier(n)
    yield n
    notify.set_notifier(notify.NullNotifier())


async def make_user(name: str = "Ali", registered: bool = True) -> int:
    async with uow() as s:
        u = User(telegram_id=next(_tg_ids), first_name=name, lang="uz")
        if registered:
            u.phone = "+998901234567"
            u.terms_accepted_at = now()
            u.terms_version = "1"
        s.add(u)
        await s.flush()
        return u.id


async def make_carrier(name: str = "Haydovchi", categories=("PASSENGER", "PARCEL"), seats=4, weight=200):
    uid = await make_user(name)
    async with uow() as s:
        v = Vehicle(user_id=uid, vehicle_type="SEDAN", make_model="Cobalt", plate_number="01A123BC", seats=seats, max_weight_kg=weight)
        s.add(v)
        s.add(CarrierProfile(user_id=uid, status=CarrierStatus.APPROVED, full_name=name))
        for c in categories:
            s.add(CarrierPermission(user_id=uid, category=c))
        await s.flush()
        return uid, v.id


async def make_admin(role: str = AdminRole.SUPERADMIN) -> int:
    from app.security import hash_password

    async with uow() as s:
        a = AdminUser(username=f"admin{next(_tg_ids)}", password_hash=hash_password("secret123"), role=role)
        s.add(a)
        await s.flush()
        return a.id


async def loc(name_uz: str) -> int:
    async with uow() as s:
        return (await s.execute(select(Location.id).where(Location.name_uz == name_uz))).scalar_one()


def future(hours: float = 24) -> datetime:
    return now() + timedelta(hours=hours)


def jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 10, 10)).save(buf, "JPEG")
    return buf.getvalue()


async def passenger_request(client_id: int, price: int = 150_000, **over) -> int:
    from app.services import listings

    data = {
        "kind": "REQUEST",
        "category": "PASSENGER",
        "from_location_id": await loc("Toshkent"),
        "to_location_id": await loc("Samarqand"),
        "departure_at": future(24),
        "price": price,
        "passengers": 1,
        "luggage": "1 sumka",
        "from_address": "Chilonzor 1",
        "to_address": "Registon",
        **over,
    }
    async with uow() as s:
        user = await s.get(User, client_id)
        return (await listings.create(s, user, data)).id


async def passenger_route(carrier_id: int, vehicle_id: int, seats: int = 3, price: int = 120_000) -> int:
    from app.services import listings

    data = {
        "kind": "ROUTE",
        "category": "PASSENGER",
        "from_location_id": await loc("Toshkent"),
        "to_location_id": await loc("Samarqand"),
        "departure_at": future(24),
        "price": price,
        "vehicle_id": vehicle_id,
        "seats": seats,
    }
    async with uow() as s:
        user = await s.get(User, carrier_id)
        return (await listings.create(s, user, data)).id
