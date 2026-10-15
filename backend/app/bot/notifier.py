"""Delivers outbox messages through Telegram with rate limiting (~20 msg/s, below Telegram's 30/s cap)."""

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup

from app.bot import keyboards
from app.db import uow
from app.i18n import has, money, t
from app.models import Listing, Location, Order, User
from app.services.notify import ADMIN_CHAT, Message
from app.timeutil import fmt

log = logging.getLogger(__name__)
ADMIN_LANG = "uz"


async def _route(s, from_id: int, to_id: int, lang: str) -> str:
    a, b = await s.get(Location, from_id), await s.get(Location, to_id)
    return f"{a.name(lang)} → {b.name(lang)}"


async def enrich(s, params: dict, lang: str) -> dict:
    p = dict(params)
    src = None
    if "order_id" in p:
        src = await s.get(Order, p["order_id"])
    elif "listing_id" in p:
        src = await s.get(Listing, p["listing_id"])
    if src is not None:
        p.setdefault("route", await _route(s, src.from_location_id, src.to_location_id, lang))
        p.setdefault("date", fmt(src.departure_at))
        p.setdefault("price", src.price)
        p.setdefault("category", t(lang, f"cat.{src.category}"))
    if isinstance(p.get("price"), int):
        p["price"] = money(p["price"])
    if isinstance(p.get("reason"), str) and has(f"reason.{p['reason']}"):
        p["reason"] = t(lang, f"reason.{p['reason']}")
    if isinstance(p.get("categories"), list):
        p["categories"] = ", ".join(t(lang, f"cat.{c}") for c in p["categories"])
    return p


class TelegramNotifier:
    def __init__(self, bot: Bot, admin_chat_id: int | None):
        self.bot = bot
        self.admin_chat_id = admin_chat_id
        self.queue: asyncio.Queue[tuple[int, str, InlineKeyboardMarkup | None, int | None]] = asyncio.Queue()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()

    async def deliver(self, messages: list[Message]) -> None:
        async with uow() as s:
            for m in messages:
                if m.user_id == ADMIN_CHAT:
                    if not self.admin_chat_id:
                        continue
                    chat_id, lang, user_id, buttons = self.admin_chat_id, ADMIN_LANG, None, None
                else:
                    user = await s.get(User, m.user_id)
                    if user is None or user.bot_blocked:
                        continue
                    chat_id, lang, user_id = user.telegram_id, user.lang, user.id
                    buttons = keyboards.from_buttons(m.buttons, lang)
                text = t(lang, m.key, **await enrich(s, m.params, lang))
                self.queue.put_nowait((chat_id, text, buttons, user_id))

    async def _worker(self) -> None:
        while True:
            chat_id, text, markup, user_id = await self.queue.get()
            for attempt in range(3):
                try:
                    await self.bot.send_message(chat_id, text, reply_markup=markup, parse_mode=None)
                    break
                except TelegramRetryAfter as e:
                    await asyncio.sleep(e.retry_after + 1)
                except TelegramForbiddenError:
                    if user_id is not None:
                        async with uow() as s:
                            u = await s.get(User, user_id)
                            if u:
                                u.bot_blocked = True
                    break
                except Exception:
                    log.exception("send_message failed (chat=%s, attempt=%s)", chat_id, attempt)
                    await asyncio.sleep(2)
            await asyncio.sleep(0.05)
