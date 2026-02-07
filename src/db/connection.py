"""Database connection management for Neon Postgres"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_current_loop_id: int | None = None


def _get_loop_id() -> int:
    """Get the current event loop's id"""
    try:
        loop = asyncio.get_event_loop()
        return id(loop)
    except RuntimeError:
        return 0


def _reset_engine() -> None:
    """Reset the engine (call when event loop changes)"""
    global _engine, _session_factory, _current_loop_id
    _engine = None
    _session_factory = None
    _current_loop_id = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine"""
    global _engine, _current_loop_id
    
    # Check if event loop changed - if so, reset engine
    current_loop = _get_loop_id()
    if _current_loop_id is not None and _current_loop_id != current_loop:
        _reset_engine()
    
    if _engine is None:
        settings = get_settings()
        # Convert postgresql:// to postgresql+asyncpg://
        db_url = settings.neon_database_url
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        # Remove query params that asyncpg doesn't understand from URL
        # asyncpg handles SSL via connect_args instead
        if "?" in db_url:
            db_url = db_url.split("?")[0]
        
        _engine = create_async_engine(
            db_url,
            echo=False,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=False,  # Disable pre-ping to avoid loop issues
            connect_args={
                "ssl": "require",  # Enable SSL for Neon
            },
        )
        _current_loop_id = current_loop
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get the async session factory"""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database tables"""
    from src.db.models import Base
    
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections"""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
