from src.api.routes.trades import router as trades_router
from src.api.routes.performance import router as performance_router
from src.api.routes.bot_control import router as bot_control_router

__all__ = ["trades_router", "performance_router", "bot_control_router"]
