"""Transactional outbox for user notifications.

Services call `queue(...)` inside a unit of work; messages are delivered only after
the transaction commits (see app.db.uow), so a rolled-back action never notifies anyone.
"""

import logging
from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

ADMIN_CHAT = -1  # pseudo user id meaning "moderators' Telegram group"


@dataclass
class Button:
    text_key: str
    callback: str | None = None  # callback_data for quick actions
    webapp_path: str | None = None  # opens Mini App at this path, e.g. "/orders/5"


@dataclass
class Message:
    user_id: int
    key: str
    params: dict = field(default_factory=dict)
    buttons: list[list[Button]] = field(default_factory=list)


class Notifier(Protocol):
    async def deliver(self, messages: list[Message]) -> None: ...


class NullNotifier:
    async def deliver(self, messages: list[Message]) -> None:
        for m in messages:
            log.info("notify (no bot) user=%s key=%s params=%s", m.user_id, m.key, m.params)


_notifier: Notifier = NullNotifier()


def set_notifier(n: Notifier) -> None:
    global _notifier
    _notifier = n


def get_notifier() -> Notifier:
    return _notifier


def queue(session: AsyncSession, user_id: int, key: str, /, buttons: list[list[Button]] | None = None, **params) -> None:
    session.info.setdefault("outbox", []).append(Message(user_id, key, params, buttons or []))


def queue_admin(session: AsyncSession, key: str, /, **params) -> None:
    queue(session, ADMIN_CHAT, key, **params)


async def dispatch(messages: list[Message]) -> None:
    try:
        await _notifier.deliver(messages)
    except Exception:  # notifications must never break a committed business action
        log.exception("notification dispatch failed")
