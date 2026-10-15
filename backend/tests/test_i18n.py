import re
from pathlib import Path

from conftest import make_carrier, make_user, passenger_request

from app.bot.notifier import enrich
from app.db import uow
from app.enums import CANCEL_REASONS, COMPLAINT_REASONS, Category
from app.i18n import has, keys, t
from app.models import User
from app.services import offers

APP = Path(__file__).resolve().parents[1] / "app"


def test_uz_and_ru_have_same_keys():
    assert keys("uz") == keys("ru")


def test_every_notification_and_button_key_is_translated():
    source = "\n".join(p.read_text(encoding="utf-8") for p in APP.rglob("*.py"))
    used = set(re.findall(r'queue(?:_admin)?\(\s*session,\s*(?:[\w.]+,\s*)?"([a-z_.]+)"', source))
    used |= set(re.findall(r'Button\("([a-z_.]+)"', source))
    used |= set(re.findall(r'"(btn\.[a-z_]+)"', source))
    assert len(used) > 25
    missing = sorted(k for k in used if not has(k))
    assert not missing, missing
    for code in [*CANCEL_REASONS, *COMPLAINT_REASONS]:
        assert has(f"reason.{code}"), code
    for c in Category:
        assert has(f"cat.{c}")


async def test_notification_text_is_rendered_in_user_language():
    client = await make_user()
    carrier, vehicle = await make_carrier()
    listing_id = await passenger_request(client, price=150_000)
    async with uow() as s:
        await offers.create(s, await s.get(User, carrier), listing_id, {"price": 1_250_000, "vehicle_id": vehicle})
    async with uow() as s:
        p = await enrich(s, {"listing_id": listing_id, "price": 1_250_000, "from_name": "Karim"}, "ru")
    text = t("ru", "offer.new", **p)
    assert "Ташкент → Самарканд" in text and "1 250 000" in text and "{" not in text
