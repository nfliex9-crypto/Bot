import sys
import os
from loguru import logger
from app.config import settings


LOG_DIR = os.environ.get("LOG_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"))
os.makedirs(LOG_DIR, exist_ok=True)


def setup_logger():
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Console output
    logger.add(
        sys.stdout,
        format=log_format,
        level="DEBUG" if settings.DEBUG else "INFO",
        colorize=True,
    )

    # General log file
    logger.add(
        f"{LOG_DIR}/trading_bot.log",
        format=log_format,
        level="INFO",
        rotation="1 day",
        retention="30 days",
        compression="gz",
        enqueue=True,
    )

    # Error-only log file
    logger.add(
        f"{LOG_DIR}/errors.log",
        format=log_format,
        level="ERROR",
        rotation="1 week",
        retention="90 days",
        compression="gz",
        enqueue=True,
    )

    # Trade-specific log
    logger.add(
        f"{LOG_DIR}/trades.log",
        format=log_format,
        level="INFO",
        filter=lambda r: "TRADE" in r["message"] or r.get("extra", {}).get("trade_log"),
        rotation="1 day",
        retention="60 days",
        compression="gz",
        enqueue=True,
    )

    return logger


def get_logger(name: str = "trading_bot"):
    return logger.bind(name=name)


setup_logger()
