"""Unit tests for the in-memory Broadcast pub-sub."""

import asyncio

import pytest

from switchboard.broadcast import Broadcast, Event


@pytest.fixture
async def broadcast() -> Broadcast:
    b = Broadcast()
    await b.connect()
    return b


async def test_single_subscriber_receives_message(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch") as sub:
        await broadcast.publish("ch", "hello")
        event = await asyncio.wait_for(sub.__anext__(), timeout=1)
    assert event == Event(channel="ch", message="hello")


async def test_multiple_subscribers_receive_same_message(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch") as sub1, broadcast.subscribe("ch") as sub2:
        await broadcast.publish("ch", "msg")
        e1 = await asyncio.wait_for(sub1.__anext__(), timeout=1)
        e2 = await asyncio.wait_for(sub2.__anext__(), timeout=1)
    assert e1.message == "msg"
    assert e2.message == "msg"


async def test_publish_to_other_channel_not_received(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch-a") as sub:
        await broadcast.publish("ch-b", "nope")
        assert sub._queue.empty()


async def test_subscriber_cleanup_after_context_exit(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch"):
        assert "ch" in broadcast._channels
    assert "ch" not in broadcast._channels


async def test_disconnect_signals_all_subscribers(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch") as sub:
        await broadcast.disconnect()
        event = await asyncio.wait_for(sub._queue.get(), timeout=1)
    assert event is None


async def test_publish_with_no_subscribers(broadcast: Broadcast) -> None:
    await broadcast.publish("nobody-listening", "echo")


async def test_subscriber_iteration(broadcast: Broadcast) -> None:
    collected: list[str] = []

    async def consume() -> None:
        async with broadcast.subscribe("ch") as sub:
            async for event in sub:
                collected.append(event.message)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.01)
    await broadcast.publish("ch", "one")
    await broadcast.publish("ch", "two")
    await asyncio.sleep(0.01)
    await broadcast.disconnect()
    await asyncio.wait_for(task, timeout=1)

    assert collected == ["one", "two"]
