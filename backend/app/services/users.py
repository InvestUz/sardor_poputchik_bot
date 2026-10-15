from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enums import Lang
from app.models import AdminUser, User
from app.services import audit
from app.services import settings as settings_svc
from app.services.errors import DomainError
from app.timeutil import now


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    return (await session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()


async def get_or_create(session: AsyncSession, tg_user: dict) -> tuple[User, bool]:
    """tg_user: Telegram user object as dict (id, first_name, last_name, username, language_code)."""
    user = await get_by_telegram_id(session, int(tg_user["id"]))
    created = user is None
    if user is None:
        lang = Lang.RU if (tg_user.get("language_code") or "").startswith("ru") else Lang.UZ
        user = User(telegram_id=int(tg_user["id"]), lang=lang)
        session.add(user)
    user.first_name = (tg_user.get("first_name") or "")[:128]
    user.last_name = (tg_user.get("last_name") or None) and tg_user["last_name"][:128]
    user.username = tg_user.get("username")
    user.bot_blocked = False
    await session.flush()
    return user, created


def set_lang(user: User, lang: str) -> None:
    if lang not in (Lang.UZ, Lang.RU):
        raise DomainError("invalid_input")
    user.lang = lang


def set_phone(user: User, phone: str) -> None:
    phone = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    if not phone.startswith("+"):
        phone = "+" + phone
    if not 8 <= len(phone) <= 16:
        raise DomainError("invalid_input")
    user.phone = phone


async def accept_terms(session: AsyncSession, user: User) -> None:
    user.terms_version = await settings_svc.get(session, "terms_version")
    user.terms_accepted_at = now()


def ensure_active(user: User | None) -> User:
    if user is None or not user.is_registered:
        raise DomainError("not_registered", 403)
    if user.is_blocked:
        raise DomainError("user_blocked", 403)
    return user


def block(session: AsyncSession, user: User, reason: str, admin: AdminUser) -> None:
    if not reason.strip():
        raise DomainError("reason_required")
    user.is_blocked = True
    user.block_reason = reason.strip()
    audit.log_admin(session, admin, "user.block", "user", user.id, reason=reason)


def unblock(session: AsyncSession, user: User, admin: AdminUser) -> None:
    user.is_blocked = False
    user.block_reason = None
    audit.log_admin(session, admin, "user.unblock", "user", user.id)
