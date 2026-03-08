import asyncio
import signal

from app.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.logging import configure_logging
from app.trading.engine import TradingEngine


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    await init_db()
    engine = TradingEngine(settings=settings, session_factory=SessionLocal)
    await engine.start(mode=settings.mode)

    stop_event = asyncio.Event()

    def _stop(*_args) -> None:
        stop_event.set()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    await stop_event.wait()
    await engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
