"""
Logger shim – delegates to the centralized logging_config module.

All existing imports of `get_logger` continue to work unchanged.
"""
from app.utils.logging_config import get_structured_logger as get_logger  # noqa: F401

__all__ = ["get_logger"]
