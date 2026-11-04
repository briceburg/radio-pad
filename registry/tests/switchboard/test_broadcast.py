"""Unit tests for the in-memory Broadcast pub-sub."""

import asyncio

import pytest

from switchboard.broadcast import Broadcast

RADIO_DIAL_EVENT = '{"event":"radio_dial_state","data":{"url":"http://example.com/dial","revision":"v1"}}'
PLAYING_KEXP = (
    '{"event":"playback_state","data":{"call_sign":"KEXP","requested_call_sign":null,"failed_call_sign":null}}'
)
PLAYING_WWOZ = (
    '{"event":"playback_state","data":{"call_sign":"WWOZ","requested_call_sign":null,"failed_call_sign":null}}'
)


@pytest.fixture
async def broadcast() -> Broadcast:
    return Broadcast()


async def test_single_subscriber_receives_message(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch") as sub:
        await broadcast.publish("ch", "hello")
        event = await asyncio.wait_for(sub.__anext__(), timeout=1)
    assert event == "hello"


async def test_multiple_subscribers_receive_same_message(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch") as sub1, broadcast.subscribe("ch") as sub2:
        await broadcast.publish("ch", "msg")
        e1 = await asyncio.wait_for(sub1.__anext__(), timeout=1)
        e2 = await asyncio.wait_for(sub2.__anext__(), timeout=1)
    assert e1 == "msg"
    assert e2 == "msg"


async def test_publish_to_other_channel_not_received(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch-a") as sub:
        await broadcast.publish("ch-b", "nope")
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(anext(sub), timeout=0.01)


async def test_subscriber_cleanup_after_context_exit(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch"):
        assert "ch" in broadcast._channels
    assert "ch" not in broadcast._channels


async def test_disconnect_signals_all_subscribers(broadcast: Broadcast) -> None:
    async with broadcast.subscribe("ch") as sub:
        await broadcast.disconnect()
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(anext(sub), timeout=1)


async def test_publish_with_no_subscribers(broadcast: Broadcast) -> None:
    await broadcast.publish("nobody-listening", "echo")


async def test_slow_subscriber_is_disconnected_without_blocking_healthy_subscriber() -> None:
    broadcast = Broadcast(subscriber_queue_size=1)

    async with broadcast.subscribe("ch") as slow, broadcast.subscribe("ch") as healthy:
        await broadcast.publish("ch", "one")
        assert await anext(healthy) == "one"
        await broadcast.publish("ch", "two")
        assert await anext(healthy) == "two"
        with pytest.raises(StopAsyncIteration):
            await anext(slow)
        await broadcast.publish("ch", "three")
        assert await anext(healthy) == "three"


async def test_replay_can_exceed_live_queue_limit() -> None:
    broadcast = Broadcast(subscriber_queue_size=1)
    broadcast.set_state("ch", "first", "one")
    broadcast.set_state("ch", "second", "two")

    async with broadcast.subscribe("ch", replay=True) as sub:
        assert [await anext(sub), await anext(sub)] == ["one", "two"]


async def test_subscriber_iteration(broadcast: Broadcast) -> None:
    collected: list[str] = []
    subscribed = asyncio.Event()
    received = asyncio.Event()

    async def consume() -> None:
        async with broadcast.subscribe("ch") as sub:
            subscribed.set()
            async for event in sub:
                collected.append(event)
                if len(collected) == 2:
                    received.set()

    task = asyncio.create_task(consume())
    await asyncio.wait_for(subscribed.wait(), timeout=1)
    await broadcast.publish("ch", "one")
    await broadcast.publish("ch", "two")
    await asyncio.wait_for(received.wait(), timeout=1)
    await broadcast.disconnect()
    await asyncio.wait_for(task, timeout=1)

    assert collected == ["one", "two"]


# -- state replay --


async def test_set_state_replayed_on_subscribe(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "radio_dial_state", RADIO_DIAL_EVENT)
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)

    async with broadcast.subscribe("ch", replay=True) as sub:
        e1 = await asyncio.wait_for(sub.__anext__(), timeout=1)
        e2 = await asyncio.wait_for(sub.__anext__(), timeout=1)

    assert [e1, e2] == [RADIO_DIAL_EVENT, PLAYING_KEXP]


async def test_no_replay_without_flag(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)

    async with broadcast.subscribe("ch") as sub:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(anext(sub), timeout=0.01)


async def test_clear_state_removes_retained(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)
    broadcast.clear_state("ch")

    async with broadcast.subscribe("ch", replay=True) as sub:
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(anext(sub), timeout=0.01)


async def test_disconnect_clears_state(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)
    await broadcast.disconnect()
    assert broadcast._channel_state == {}


async def test_set_state_replaces_existing_key(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)
    broadcast.set_state("ch", "playback_state", PLAYING_WWOZ)

    async with broadcast.subscribe("ch", replay=True) as sub:
        event = await asyncio.wait_for(sub.__anext__(), timeout=1)

    assert event == PLAYING_WWOZ


async def test_clear_state_key_removes_one_retained_item(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "player_status:switchboard", "switchboard")
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)
    broadcast.clear_state_key("ch", "player_status:switchboard")

    async with broadcast.subscribe("ch", replay=True) as sub:
        event = await asyncio.wait_for(sub.__anext__(), timeout=1)

    assert event == PLAYING_KEXP
