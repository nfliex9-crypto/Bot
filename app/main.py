from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.core.config import get_settings
from app.db.base import build_engine, build_session_factory
from app.services.engine import TradingEngine
from app.services.repository import TradingRepository


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = build_engine(settings)
    session_factory = build_session_factory(settings, engine=engine)
    repository = TradingRepository(session_factory, engine)
    repository.create_schema()
    repository.set_bot_mode(settings.bot_mode)
    repository.set_bot_enabled(settings.bot_enabled_on_startup)

    trading_engine = TradingEngine(settings, repository)
    app.state.settings = settings
    app.state.repository = repository
    app.state.engine = trading_engine

    await trading_engine.start_background()
    try:
        yield
    finally:
        await trading_engine.shutdown()


app = FastAPI(title="AI Trading Bot", version="0.1.0", lifespan=lifespan)
app.include_router(router)
