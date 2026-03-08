import sys
import os
from loguru import logger
from config.settings import settings


def setup_logging() -> None:
    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(sys.stdout, format=log_format, level=settings.log_level, colorize=True)

    os.makedirs(settings.log_dir, exist_ok=True)

    logger.add(
        os.path.join(settings.log_dir, "trading_bot_{time:YYYY-MM-DD}.log"),
        format=log_format,
        level=settings.log_level,
        rotation="00:00",
        retention="30 days",
        compression="gz",
        enqueue=True,
    )

    logger.add(
        os.path.join(settings.log_dir, "trades_{time:YYYY-MM-DD}.log"),
        format=log_format,
        level="INFO",
        rotation="00:00",
        retention="90 days",
        filter=lambda record: "TRADE" in record["message"],
        enqueue=True,
    )

    logger.add(
        os.path.join(settings.log_dir, "errors_{time:YYYY-MM-DD}.log"),
        format=log_format,
        level="ERROR",
        rotation="00:00",
        retention="60 days",
        compression="gz",
        enqueue=True,
    )
