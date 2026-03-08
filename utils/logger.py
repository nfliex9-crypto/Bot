from __future__ import annotations

import logging
import sys
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def _configure_root() -> None:
    root = logging.getLogger()
    if root.handlers:
        return

    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # Console
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)

    # Rotating file
    from logging.handlers import RotatingFileHandler

    fh = RotatingFileHandler(
        LOG_DIR / "trading_bot.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(formatter)

    root.addHandler(sh)
    root.addHandler(fh)

    try:
        from config.settings import settings
        root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    except Exception:
        root.setLevel(logging.INFO)


_configure_root()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
