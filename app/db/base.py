from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


def build_engine(settings: Settings):
    return create_engine(settings.database_url, future=True, pool_pre_ping=True)


def build_session_factory(settings: Settings, engine: Engine | None = None):
    engine = engine or build_engine(settings)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
