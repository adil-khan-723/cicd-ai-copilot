"""
In-memory pub/sub connecting sync pipeline stages to async SSE stream.

publish() is fully thread-safe — background threads (run_in_executor) call
loop.call_soon_threadsafe so events are enqueued on the event loop thread,
not from the worker thread.

subscribe() is an async generator that:
  1. Replays recent history to the new subscriber immediately on connect
  2. Then streams live events as they arrive

This means a browser that connects AFTER a build completes still sees the
full failure card — it doesn't have to be open before the build starts.
"""
import asyncio
import json
import logging
from collections import deque
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# How many past events to replay to new subscribers
_HISTORY_SIZE = 200


class EventBus:
    def __init__(self) -> None:
        self._queues: list[asyncio.Queue] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        # Ring buffer of recent events — replayed to late-joining subscribers
        self._history: deque[dict] = deque(maxlen=_HISTORY_SIZE)

    async def subscribe(self) -> AsyncGenerator[str, None]:
        """
        Async generator — first replays history, then streams live events.
        Safe to call from multiple concurrent browser tabs.
        """
        self._loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)

        # Snapshot history before registering the queue so we don't
        # double-deliver events that arrive during the replay
        history_snapshot = list(self._history)
        self._queues.append(queue)

        try:
            # Replay past events to this new subscriber
            for event in history_snapshot:
                yield f"data: {json.dumps(event)}\n\n"

            # Stream live events
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

        Stores the event in history (for late-joining subscribers) and
        delivers it to all currently connected subscribers.

        Uses call_soon_threadsafe when called from a background thread so
        asyncio.Queue is only touched from the event loop thread.
        """
        # Drop duplicate analysis_complete events for same job+build — prevents
        # double cards when both notification plugin and pipeline-failure endpoint fire.
        if event.get("type") == "analysis_complete":
            job, build = event.get("job"), event.get("build")
            for past in self._history:
                if (past.get("type") == "analysis_complete"
                        and past.get("job") == job
                        and past.get("build") == build):
                    logger.debug("EventBus: dropped duplicate analysis_complete for %s #%s", job, build)
                    return

        # Store in history immediately (deque is thread-safe for append)
        self._history.append(event)

        loop = self._loop
        if loop is None or not loop.is_running():
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
            pass


# Module-level singleton shared across webhook and UI routes
bus = EventBus()
