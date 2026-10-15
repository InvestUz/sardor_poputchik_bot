"""Management commands.

    python -m app.cli create-admin <username> <SUPERADMIN|MODERATOR|SUPPORT>   (password is asked interactively)
    python -m app.cli seed
    python -m app.cli run-jobs
    python -m app.cli dev-user <telegram_id> <name>      (DEBUG only: registered test user)
"""

import asyncio
import getpass
import sys

from sqlalchemy import select

from app.config import settings
from app.db import init_engine, uow
from app.enums import AdminRole
from app.models import AdminUser
from app.security import hash_password
from app.services import jobs, locations, users


async def create_admin(username: str, role: str) -> None:
    if role not in AdminRole.__members__:
        sys.exit(f"role must be one of {list(AdminRole.__members__)}")
    password = getpass.getpass("Password (min 10 chars): ")
    if len(password) < 10 or password != getpass.getpass("Repeat: "):
        sys.exit("passwords do not match or too short")
    async with uow() as s:
        existing = (await s.execute(select(AdminUser).where(AdminUser.username == username))).scalar_one_or_none()
        if existing:
            existing.password_hash, existing.role, existing.is_active = hash_password(password), role, True
            print("admin updated")
        else:
            s.add(AdminUser(username=username, password_hash=hash_password(password), role=role))
            print("admin created")


async def dev_user(telegram_id: int, name: str) -> None:
    """Local testing only: a registered user without going through the bot."""
    if not settings.debug:
        sys.exit("dev-user is only available with DEBUG=true")
    async with uow() as s:
        user, _ = await users.get_or_create(s, {"id": telegram_id, "first_name": name})
        users.set_phone(user, f"+99890{telegram_id % 10_000_000:07d}")
        await users.accept_terms(s, user)
    print(f"user {name} ({telegram_id}) ready: open /app/?dev={telegram_id}")


async def main(argv: list[str]) -> None:
    init_engine(settings.database_url)
    match argv:
        case ["create-admin", username, role]:
            await create_admin(username, role)
        case ["seed"]:
            async with uow() as s:
                print("locations added:", await locations.seed_if_empty(s))
        case ["run-jobs"]:
            print(await jobs.run_once())
        case ["dev-user", telegram_id, name]:
            await dev_user(int(telegram_id), name)
        case _:
            print(__doc__)


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
