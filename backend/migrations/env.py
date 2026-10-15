import asyncio

import sqlalchemy as sa
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app import models  # noqa: F401  (registers tables)
from app.config import settings
from app.db import Base, UTCDateTime

target_metadata = Base.metadata


def render_item(type_, obj, autogen_context):
    # render our tz-aware wrapper as a plain DateTime(timezone=True) so migrations do not import app code
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _configure(**kw):
    context.configure(
        target_metadata=target_metadata,
        render_item=render_item,
        render_as_batch=settings.is_sqlite,
        compare_type=True,
        **kw,
    )


def run_offline() -> None:
    _configure(url=settings.database_url, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run_sync(connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(settings.database_url)
    async with engine.connect() as conn:
        await conn.run_sync(_run_sync)
    await engine.dispose()


if context.is_offline_mode():
    run_offline()
else:
    asyncio.run(run_online())

_ = sa
