"""Async SQLAlchemy session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config.settings import AppSettings

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(settings: AppSettings):
    global _engine, _session_factory
    _engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


def get_engine():
    assert _engine is not None, "Engine not initialised — call init_engine first"
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    assert _session_factory is not None, "Session factory not initialised"
    return _session_factory


async def create_tables():
    from app.db.models import Base
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
