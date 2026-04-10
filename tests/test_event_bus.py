import asyncio
import pytest
from ui.event_bus import EventBus


@pytest.mark.asyncio
async def test_subscribe_receives_published_event():
    bus = EventBus()
    events = []

    async def collect():
        async for chunk in bus.subscribe():
            events.append(chunk)
            break  # take one event then stop

    task = asyncio.create_task(collect())
    await asyncio.sleep(0.01)  # let subscriber register
    bus.publish({"type": "step", "stage": "LOG_EXTRACTED"})
    await asyncio.wait_for(task, timeout=1.0)

    assert len(events) == 1
    assert '"LOG_EXTRACTED"' in events[0]


@pytest.mark.asyncio
async def test_multiple_subscribers_each_receive_event():
    bus = EventBus()
    received = []

    async def collect(n):
        async for chunk in bus.subscribe():
            received.append(n)
            break

    tasks = [asyncio.create_task(collect(i)) for i in range(3)]
    await asyncio.sleep(0.01)
    bus.publish({"type": "step", "stage": "TEST"})
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=1.0)

    assert sorted(received) == [0, 1, 2]


@pytest.mark.asyncio
async def test_publish_with_no_subscribers_does_not_raise():
    bus = EventBus()
    bus.publish({"type": "step", "stage": "NOOP"})  # should not raise
