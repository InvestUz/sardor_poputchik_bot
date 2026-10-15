from fastapi import Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User
from app.security import InvalidInitData, validate_init_data
from app.services import users
from app.services.errors import DomainError


async def tg_user(authorization: str = Header("")) -> dict:
    """Authenticates a Mini App request by its Telegram initData signature."""
    scheme, _, value = authorization.partition(" ")
    if scheme == "tma":
        try:
            return validate_init_data(value, settings.bot_token, settings.init_data_ttl_seconds)
        except InvalidInitData:
            raise DomainError("invalid_init_data", 401)
    if scheme == "dev" and settings.debug and value.isdigit():
        return {"id": int(value), "first_name": f"Dev{value}"}
    raise DomainError("invalid_init_data", 401)


async def current_user(session: AsyncSession, tg: dict) -> User:
    return users.ensure_active(await users.get_by_telegram_id(session, int(tg["id"])))
