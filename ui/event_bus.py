"""
In-memory pub/sub connecting sync pipeline stages to async SSE stream.

publish() is safe to call from a sync thread (uses put_nowait).
subscribe() is an async generator yielding SSE-formatted strings.
"""
import asyncio
import json
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Async generator — yields SSE data lines for each published event."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.append(queue)
        try:
            while True:
                event = await queue.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            try:
                self._queues.remove(queue)
            except ValueError:
                pass

    def publish(self, event: dict) -> None:
        """
        Thread-safe publish from sync context.
        Drops the event silently if a subscriber queue is full.
        """
        for queue in list(self._queues):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning("EventBus: dropped event (subscriber queue full)")


# Module-level singleton shared across webhook and UI routes
bus = EventBus()
