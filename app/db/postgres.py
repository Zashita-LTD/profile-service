"""PostgreSQL async connection."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


# Engine and session factory
_engine = None
_async_session_factory = None


async def init_postgres() -> None:
    """Initialize PostgreSQL connection."""
    global _engine, _async_session_factory
    
    settings = get_settings()
    _engine = create_async_engine(
        settings.postgres_url,
        echo=settings.api_debug,
        pool_size=10,
        max_overflow=20,
    )
    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Create tables
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_postgres() -> None:
    """Close PostgreSQL connection."""
    global _engine
    if _engine:
        await _engine.dispose()


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    if not _async_session_factory:
        raise RuntimeError("PostgreSQL not initialized")
    
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
