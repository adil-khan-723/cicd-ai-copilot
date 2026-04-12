"""
In-memory pub/sub connecting sync pipeline stages to async SSE stream.

publish() is fully thread-safe — background threads (run_in_executor) call
loop.call_soon_threadsafe so events are enqueued on the event loop thread,
not from the worker thread.

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
        self._loop: asyncio.AbstractEventLoop | None = None

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """Async generator — yields SSE data lines for each published event."""
        # Capture the running loop so publish() can schedule onto it safely.
        self._loop = asyncio.get_running_loop()
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
        Thread-safe publish from any context (sync worker thread or async).

        If called from a background thread (run_in_executor), uses
        call_soon_threadsafe so the put_nowait runs on the event loop thread —
        asyncio.Queue is not thread-safe and must only be touched from the loop.

        Falls back to direct put_nowait when already on the loop thread.
        """
        loop = self._loop
        if loop is None or not loop.is_running():
            # No subscriber yet or loop stopped — try direct (best effort)
            for queue in list(self._queues):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("EventBus: dropped event (queue full, no loop)")
            return

        def _enqueue():
            for queue in list(self._queues):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    logger.warning("EventBus: dropped event (subscriber queue full)")

        try:
            loop.call_soon_threadsafe(_enqueue)
        except RuntimeError:
            # Loop closed between the check and the call
            pass


# Module-level singleton shared across webhook and UI routes
bus = EventBus()
