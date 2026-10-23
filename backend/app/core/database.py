"""
StockSense AI - Database Engine & Session Management

Provides async SQLAlchemy engine and session factory.
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import create_engine
from app.core.config import settings


# Engine kwargs based on DB driver
async_engine_kwargs = {"echo": settings.DEBUG}
if "sqlite" not in settings.DATABASE_URL:
    async_engine_kwargs.update({
        "pool_size": 10,
        "max_overflow": 20,
        "pool_pre_ping": True,
    })

# Async engine for FastAPI
async_engine = create_async_engine(
    settings.DATABASE_URL,
    **async_engine_kwargs,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

sync_engine_kwargs = {"echo": settings.DEBUG}
if "sqlite" not in settings.DATABASE_URL_SYNC:
    sync_engine_kwargs["pool_pre_ping"] = True

# Sync engine for Alembic migrations and seed scripts
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    **sync_engine_kwargs,
)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


async def get_db() -> AsyncSession:
    """FastAPI dependency that provides an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
