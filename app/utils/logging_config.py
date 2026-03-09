"""
Centralized Structured Logging.

Replaces the previous loguru-only setup with a hybrid approach:
  - Python stdlib `logging` as the primary handler interface
  - loguru as the sink (format + rotation + colour)
  - JSON formatter for production log shipping (Fluentd, Loki, etc.)
  - Separate named log files:
      trading.log   – all INFO+ events
      errors.log    – ERROR+ only
      trades.log    – trade executions
      ai.log        – model predictions and training events
  - Structured extra fields (symbol, trade_id, confidence, …)
    accessible in log records

Usage:
    from app.utils.logging_config import get_structured_logger

    log = get_structured_logger("strategy")
    log.info("Signal generated", extra={"symbol": "EURUSD", "confidence": 0.72})
"""
import os
import sys
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Optional

from loguru import logger as loguru_logger
from app.config import settings

UTC = timezone.utc

LOG_DIR = os.environ.get(
    "LOG_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"),
)
os.makedirs(LOG_DIR, exist_ok=True)

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """
    Outputs each log record as a single-line JSON object.
    Compatible with Loki, Fluentd, Datadog log shipping.
    """

    RESERVED = {"msg", "args", "levelname", "levelno", "pathname", "filename",
                 "module", "exc_info", "exc_text", "stack_info", "lineno",
                 "funcName", "created", "msecs", "relativeCreated", "thread",
                 "threadName", "processName", "process", "name", "message"}

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add structured extra fields
        for key, value in record.__dict__.items():
            if key not in self.RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)  # ensure serialisable
                    log_entry[key] = value
                except (TypeError, ValueError):
                    log_entry[key] = str(value)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class InterceptHandler(logging.Handler):
    """
    Routes stdlib logging records into loguru.
    Ensures uvicorn, sqlalchemy, and other libraries
    appear in the same loguru stream.
    """

    def emit(self, record: logging.LogRecord):
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def configure_logging(debug: bool = False, json_output: bool = False):
    """
    One-time logging configuration.
    Call this at application startup (idempotent).
    """
    global _CONFIGURED
    if _CONFIGURED:
        return
    _CONFIGURED = True

    # ── loguru setup ──────────────────────────────────────────────────────
    loguru_logger.remove()

    console_fmt = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Console
    loguru_logger.add(
        sys.stdout,
        format=console_fmt,
        level="DEBUG" if debug else "INFO",
        colorize=True,
        enqueue=True,
    )

    # trading.log — all events
    loguru_logger.add(
        os.path.join(LOG_DIR, "trading.log"),
        format=console_fmt,
        level="INFO",
        rotation="00:00",
        retention="30 days",
        compression="gz",
        enqueue=True,
    )

    # errors.log — errors only
    loguru_logger.add(
        os.path.join(LOG_DIR, "errors.log"),
        format=console_fmt,
        level="ERROR",
        rotation="1 week",
        retention="90 days",
        compression="gz",
        enqueue=True,
    )

    # trades.log — trade lifecycle events
    loguru_logger.add(
        os.path.join(LOG_DIR, "trades.log"),
        format=console_fmt,
        level="INFO",
        filter=lambda r: (
            "TRADE" in r["message"]
            or r.get("extra", {}).get("trade_log")
        ),
        rotation="1 day",
        retention="60 days",
        compression="gz",
        enqueue=True,
    )

    # ai.log — model predictions and training
    loguru_logger.add(
        os.path.join(LOG_DIR, "ai.log"),
        format=console_fmt,
        level="INFO",
        filter=lambda r: r.get("extra", {}).get("ai_log"),
        rotation="1 week",
        retention="30 days",
        compression="gz",
        enqueue=True,
    )

    # ── stdlib interception ───────────────────────────────────────────────
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access",
                 "sqlalchemy.engine", "fastapi", "asyncio"):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False

    # ── stdlib JSON file handler (optional) ───────────────────────────────
    if json_output:
        json_handler = logging.handlers.RotatingFileHandler(
            os.path.join(LOG_DIR, "trading_json.log"),
            maxBytes=50 * 1024 * 1024,
            backupCount=5,
        )
        json_handler.setFormatter(JsonFormatter())
        json_handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(json_handler)
        root.setLevel(logging.INFO)

    loguru_logger.info(
        f"Logging configured | dir={LOG_DIR} debug={debug} json={json_output}"
    )


def get_structured_logger(name: str = "trading"):
    """
    Return a loguru logger bound to `name`.
    Supports structured extra fields via .bind() or the `extra` kwarg.
    """
    return loguru_logger.bind(logger_name=name)


# Apply at import time
configure_logging(
    debug=settings.DEBUG,
    json_output=os.environ.get("LOG_JSON", "false").lower() == "true",
)
