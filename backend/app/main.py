from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_health import router as health_router
from app.api.routes_signals import router as signals_router
from app.api.routes_trades import router as trades_router
from app.core.config import get_settings
from app.core.database import Base, engine
from app import models  # noqa: F401

settings = get_settings()
app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(signals_router)
app.include_router(trades_router)
app.include_router(dashboard_router)


@app.on_event("startup")
def startup_event() -> None:
    Base.metadata.create_all(bind=engine)
