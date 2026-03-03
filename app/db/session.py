"""
Database session management.
- Async session for FastAPI endpoints (non-blocking I/O)
- Sync session for Celery workers
"""
from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ── Async Engine (FastAPI) ─────────────────────────────────────────
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,          # Validate connections before use
    pool_recycle=3600,           # Recycle connections every hour
    echo=not settings.is_production,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# ── Sync Engine (Celery Workers) ───────────────────────────────────
sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=3600,
)

SyncSessionLocal = sessionmaker(bind=sync_engine, autoflush=False, autocommit=False)


# ── Dependency: Async DB Session ───────────────────────────────────
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Utility: Sync Session (Celery) ────────────────────────────────
def get_sync_db() -> Session:
    return SyncSessionLocal()
