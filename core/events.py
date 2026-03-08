from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List

logger = logging.getLogger(__name__)

Listener = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    """Simple async pub/sub event bus for decoupled component communication."""

    def __init__(self) -> None:
        self._listeners: Dict[str, List[Listener]] = defaultdict(list)

    def on(self, event: str, callback: Listener) -> None:
        self._listeners[event].append(callback)

    def off(self, event: str, callback: Listener) -> None:
        self._listeners[event] = [cb for cb in self._listeners[event] if cb != callback]

    async def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        for callback in self._listeners.get(event, []):
            try:
                await callback(*args, **kwargs)
            except Exception:
                logger.exception("Error in event handler for %s", event)

    async def emit_concurrent(self, event: str, *args: Any, **kwargs: Any) -> None:
        tasks = [callback(*args, **kwargs) for callback in self._listeners.get(event, [])]
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    logger.exception("Error in concurrent event handler for %s: %s", event, r)


event_bus = EventBus()
