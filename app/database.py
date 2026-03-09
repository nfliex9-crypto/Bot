"""
Database module.

Provides:
  - Async SQLAlchemy engine (asyncpg)
  - Session factory with auto-commit/rollback
  - create_tables() — idempotent DDL using SQLAlchemy metadata
  - wait_for_db()   — exponential-backoff retry until PG accepts connections
  - run_migrations()— runs Alembic programmatically (inside Docker entrypoint
                       this is done by the shell script; here it is available
                       as a Python fallback)
"""
import asyncio
import logging
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

logger = logging.getLogger("trading_bot.database")


# ── URL normalisation ─────────────────────────────────────────────────────

def _async_url(url: str) -> str:
    """Convert a postgresql:// URL to postgresql+asyncpg://."""
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix):]
    return url


def _sync_url(url: str) -> str:
    """Strip +asyncpg driver for sync psycopg2 connections (Alembic)."""
    return url.replace("+asyncpg", "")


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://trader:trading_password@postgres:5432/trading_bot",
)
ASYNC_DATABASE_URL = _async_url(DATABASE_URL)


# ── Engine ────────────────────────────────────────────────────────────────

def _engine_kwargs(url: str) -> dict:
    """Return dialect-appropriate engine keyword arguments."""
    base = dict(
        echo=os.environ.get("DEBUG", "false").lower() == "true",
        pool_pre_ping=True,
    )
    if "sqlite" in url:
        # SQLite is single-file; pooling parameters don't apply
        base["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL via asyncpg
        base.update(
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            connect_args={"server_settings": {"application_name": "ai_trading_bot"}},
        )
    return base


engine = create_async_engine(ASYNC_DATABASE_URL, **_engine_kwargs(ASYNC_DATABASE_URL))

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── ORM Base ──────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Session dependency (FastAPI) ──────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Wait-for-DB with retry ────────────────────────────────────────────────

async def wait_for_db(
    max_attempts: int = 30,
    delay: float = 2.0,
) -> bool:
    """
    Repeatedly try to connect to the database until it responds.
    Returns True on success, raises RuntimeError after max_attempts.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info(f"Database connection established (attempt {attempt})")
            return True
        except Exception as exc:
            if attempt == max_attempts:
                raise RuntimeError(
                    f"Database unreachable after {max_attempts} attempts: {exc}"
                ) from exc
            logger.warning(
                f"Database not ready (attempt {attempt}/{max_attempts}): "
                f"{type(exc).__name__} — retrying in {delay}s"
            )
            await asyncio.sleep(delay)
    return False


# ── Table management ──────────────────────────────────────────────────────

async def create_tables() -> None:
    """
    Create all tables defined via ORM metadata (idempotent).
    Also imports all models so they register with Base.metadata.
    """
    # Import models so they register with Base
    from app.models.trade import Trade          # noqa: F401
    from app.models.signal import Signal        # noqa: F401
    from app.models.performance import (        # noqa: F401
        PerformanceMetrics, SessionStats,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created / verified")


async def drop_tables() -> None:
    """Drop all tables (dev/test only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ── Alembic programmatic runner ───────────────────────────────────────────

def run_migrations() -> None:
    """
    Run Alembic migrations synchronously.
    Used as a Python fallback; the Docker entrypoint uses alembic CLI directly.
    """
    try:
        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")
        )
        alembic_cfg.set_main_option("sqlalchemy.url", _sync_url(DATABASE_URL))
        command.upgrade(alembic_cfg, "head")
        logger.info("Alembic migrations applied")
    except Exception as exc:
        logger.warning(f"Alembic migration warning (non-fatal): {exc}")
