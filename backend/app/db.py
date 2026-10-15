from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from sqlalchemy import DateTime, MetaData, event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.timeutil import UTC

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class UTCDateTime(TypeDecorator):
    """Always stores UTC and always returns timezone-aware datetimes (SQLite drops tzinfo)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime is not allowed")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(url: str, **kwargs) -> AsyncEngine:
    global _engine, _sessionmaker
    if url.startswith("sqlite"):
        kwargs.setdefault("connect_args", {"timeout": 30})
    else:
        kwargs.setdefault("pool_pre_ping", True)
    _engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(_engine.sync_engine, "connect")
        def _fk_on(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    assert _engine is not None, "init_engine() was not called"
    return _engine


@asynccontextmanager
async def uow() -> AsyncIterator[AsyncSession]:
    """Unit of work: commits on success, then delivers queued notifications."""
    from app.services import notify

    assert _sessionmaker is not None, "init_engine() was not called"
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except BaseException as exc:
            if getattr(exc, "commit", False) is True:  # DomainError(commit=True): keep the recorded side effects
                await session.commit()
            else:
                await session.rollback()
            raise
        outbox = session.info.pop("outbox", [])
    if outbox:
        await notify.dispatch(outbox)
