"""Bot flows against a fake Telegram API session (no network)."""

import itertools
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.methods import AnswerCallbackQuery, EditMessageReplyMarkup, PinChatMessage, SendMessage, TelegramMethod
from aiogram.types import Chat, Message, Update
from conftest import make_carrier, make_user, passenger_request
from sqlalchemy import select

from app.bot.handlers import router
from app.db import uow
from app.models import Order, User
from app.services import offers

_ids = itertools.count(1)


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls: list[TelegramMethod] = []

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(message_id=next(_ids), date=datetime.now(), chat=Chat(id=method.chat_id, type="private"), text=method.text)
        return True

    async def stream_content(self, *a, **kw):  # pragma: no cover
        yield b""

    async def close(self):
        pass

    def texts(self) -> list[str]:
        return [c.text for c in self.calls if isinstance(c, SendMessage)]


_dp = Dispatcher()
_dp.include_router(router)  # a router can be attached only once per process


def make_bot():
    session = FakeSession()
    bot = Bot("123456:TEST", session=session)
    return bot, _dp, session


def _user(tg_id: int) -> dict:
    return {"id": tg_id, "is_bot": False, "first_name": "Sardor", "language_code": "uz"}


def msg_update(tg_id: int, **kw) -> dict:
    return {
        "update_id": next(_ids),
        "message": {"message_id": next(_ids), "date": 0, "chat": {"id": tg_id, "type": "private"}, "from": _user(tg_id), **kw},
    }


def cb_update(tg_id: int, data: str) -> dict:
    return {
        "update_id": next(_ids),
        "callback_query": {
            "id": str(next(_ids)),
            "from": _user(tg_id),
            "chat_instance": "x",
            "data": data,
            "message": {"message_id": 1, "date": 0, "chat": {"id": tg_id, "type": "private"}, "text": "x"},
        },
    }


async def feed(bot, dp, data):
    await dp.feed_update(bot, Update.model_validate(data, context={"bot": bot}))


async def test_registration_flow():
    bot, dp, session = make_bot()
    tg = 555001
    await feed(bot, dp, msg_update(tg, text="/start"))
    assert "Tilni tanlang" in session.texts()[-1]

    await feed(bot, dp, cb_update(tg, "lang:ru"))
    assert "номер телефона" in session.texts()[-1]

    # someone else's contact is refused
    await feed(bot, dp, msg_update(tg, contact={"phone_number": "+998901112233", "first_name": "X", "user_id": 999}))
    assert "именно свой номер" in session.texts()[-1]

    await feed(bot, dp, msg_update(tg, contact={"phone_number": "998901112233", "first_name": "S", "user_id": tg}))
    assert "условиями использования" in session.texts()[-1]
    async with uow() as s:
        u = (await s.execute(select(User).where(User.telegram_id == tg))).scalar_one()
        assert u.phone == "+998901112233" and not u.is_registered and u.lang == "ru"

    await feed(bot, dp, cb_update(tg, "terms:accept"))
    async with uow() as s:
        u = (await s.execute(select(User).where(User.telegram_id == tg))).scalar_one()
        assert u.is_registered
    assert any("Главное меню" in t for t in session.texts())
    guide = next(c for c in session.calls if isinstance(c, SendMessage) and "КАК РАБОТАЕТ" in c.text)
    pin = next(c for c in session.calls if isinstance(c, PinChatMessage))
    assert pin.chat_id == tg and pin.disable_notification is True
    assert "{support}" not in guide.text

    await feed(bot, dp, msg_update(tg, text="/help"))
    assert "КАК РАБОТАЕТ" in session.texts()[-1]


async def test_quick_action_confirms_order_and_reports_errors():
    bot, dp, session = make_bot()
    client = await make_user()
    carrier, vehicle = await make_carrier()
    listing_id = await passenger_request(client)
    async with uow() as s:
        offer = await offers.create(s, await s.get(User, carrier), listing_id, {"price": 150_000, "vehicle_id": vehicle})
    async with uow() as s:
        order = await offers.accept(s, await s.get(User, client), offer.id)
        carrier_tg = (await s.get(User, carrier)).telegram_id
        client_tg = (await s.get(User, client)).telegram_id

    # the client cannot press the carrier's confirm button
    await feed(bot, dp, cb_update(client_tg, f"o:confirm:{order.id}"))
    answer = [c for c in session.calls if isinstance(c, AnswerCallbackQuery)][-1]
    assert answer.show_alert and "ruxsat" in answer.text

    await feed(bot, dp, cb_update(carrier_tg, f"o:confirm:{order.id}"))
    async with uow() as s:
        assert (await s.get(Order, order.id)).status == "CONFIRMED"
    assert any(isinstance(c, EditMessageReplyMarkup) for c in session.calls)


async def test_blocked_user_gets_block_message():
    bot, dp, session = make_bot()
    uid = await make_user()
    async with uow() as s:
        u = await s.get(User, uid)
        u.is_blocked, u.block_reason = True, "spam"
        tg = u.telegram_id
    await feed(bot, dp, msg_update(tg, text="/start"))
    assert "spam" in session.texts()[-1]
