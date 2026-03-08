from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.init_db import create_database
from app.services.ai import RandomForestConfidenceModel
from app.services.engine import TradingEngine
from app.services.execution import ExecutionRouter
from app.services.filters import TradingFilters
from app.services.news import EconomicNewsProvider
from app.services.risk import RiskManager
from app.services.strategy import LiquiditySweepBosPullbackStrategy


def build_engine() -> TradingEngine:
    settings = get_settings()
    strategy = LiquiditySweepBosPullbackStrategy(settings)
    news_provider = EconomicNewsProvider(settings)
    filters = TradingFilters(settings, news_provider)
    risk_manager = RiskManager(settings)
    ai_model = RandomForestConfidenceModel(settings)
    execution_router = ExecutionRouter(settings)
    return TradingEngine(
        settings=settings,
        strategy=strategy,
        ai_model=ai_model,
        filters=filters,
        risk_manager=risk_manager,
        execution_router=execution_router,
    )


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    create_database()
    engine = build_engine()
    engine.run_forever()


if __name__ == "__main__":
    main()
