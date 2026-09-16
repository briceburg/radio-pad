"""Unit tests for the in-memory Broadcast pub-sub."""

import asyncio

import pytest

from switchboard.broadcast import Broadcast, Event

RADIO_DIAL_EVENT = '{"event":"radio_dial_state","data":{"url":"http://example.com/dial","revision":"v1"}}'
PLAYING_KEXP = (
    '{"event":"playback_state","data":{"call_sign":"KEXP","requested_call_sign":null,"failed_call_sign":null}}'
)
PLAYING_WWOZ = (
    '{"event":"playback_state","data":{"call_sign":"WWOZ","requested_call_sign":null,"failed_call_sign":null}}'
)


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
        with pytest.raises(asyncio.QueueShutDown):
            await asyncio.wait_for(sub._queue.get(), timeout=1)


async def test_publish_with_no_subscribers(broadcast: Broadcast) -> None:
    await broadcast.publish("nobody-listening", "echo")


async def test_slow_subscriber_is_removed_when_its_queue_fills() -> None:
    broadcast = Broadcast(subscriber_queue_size=1)

    async with broadcast.subscribe("ch") as sub:
        await broadcast.publish("ch", "one")
        await broadcast.publish("ch", "two")

        assert "ch" not in broadcast._channels
        with pytest.raises(asyncio.QueueShutDown):
            await sub._queue.get()


async def test_replay_can_exceed_live_queue_limit() -> None:
    broadcast = Broadcast(subscriber_queue_size=1)
    broadcast.set_state("ch", "first", "one")
    broadcast.set_state("ch", "second", "two")

    async with broadcast.subscribe("ch", replay=True) as sub:
        assert [await anext(sub), await anext(sub)] == [Event("ch", "one"), Event("ch", "two")]


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


# -- state replay --


async def test_set_state_replayed_on_subscribe(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "radio_dial_state", RADIO_DIAL_EVENT)
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)

    async with broadcast.subscribe("ch", replay=True) as sub:
        e1 = await asyncio.wait_for(sub.__anext__(), timeout=1)
        e2 = await asyncio.wait_for(sub.__anext__(), timeout=1)

    assert [e1.message, e2.message] == [RADIO_DIAL_EVENT, PLAYING_KEXP]


async def test_no_replay_without_flag(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)

    async with broadcast.subscribe("ch") as sub:
        assert sub._queue.empty()


async def test_clear_state_removes_retained(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)
    broadcast.clear_state("ch")

    async with broadcast.subscribe("ch", replay=True) as sub:
        assert sub._queue.empty()


async def test_disconnect_clears_state(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)
    await broadcast.disconnect()
    assert broadcast._channel_state == {}


async def test_set_state_replaces_existing_key(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)
    broadcast.set_state("ch", "playback_state", PLAYING_WWOZ)

    async with broadcast.subscribe("ch", replay=True) as sub:
        event = await asyncio.wait_for(sub.__anext__(), timeout=1)

    assert event.message == PLAYING_WWOZ


async def test_clear_state_key_removes_one_retained_item(broadcast: Broadcast) -> None:
    broadcast.set_state("ch", "player_status:switchboard", "switchboard")
    broadcast.set_state("ch", "playback_state", PLAYING_KEXP)
    broadcast.clear_state_key("ch", "player_status:switchboard")

    async with broadcast.subscribe("ch", replay=True) as sub:
        event = await asyncio.wait_for(sub.__anext__(), timeout=1)

    assert event.message == PLAYING_KEXP
