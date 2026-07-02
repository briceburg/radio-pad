import asyncio
import json
from functools import wraps
from types import SimpleNamespace

from lib.interfaces import RadioPadPlayer, RadioPadStation

KEXP = RadioPadStation("KEXP", "https://example.test/kexp")
KGUT = RadioPadStation("KGUT", "https://example.test/kgut")


def async_test(test):
    @wraps(test)
    def run():
        asyncio.run(test())

    return run


class PlaybackAttempt:
    def __init__(self, success=True):
        self.success = success
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False


class ControlledPlayer(RadioPadPlayer):
    def __init__(self, attempts=None):
        super().__init__()
        self.attempts = list(attempts or [])
        self.play_calls = []

    async def play(self, station):
        attempt = self.attempts.pop(0)
        self.play_calls.append(station.call_sign)
        attempt.started.set()
        try:
            await attempt.release.wait()
        except asyncio.CancelledError:
            attempt.cancelled = True
            raise
        if attempt.success:
            self.station = station
        return attempt.success

    async def stop(self):
        self.station = None

    async def volume_up(self):
        pass

    async def volume_down(self):
        pass


@async_test
async def test_pending_transitions_to_confirmed_playback():
    attempt = PlaybackAttempt()
    player = ControlledPlayer([attempt])

    await player.request_playback(KEXP)
    assert player.requested_call_sign == "KEXP"

    await attempt.started.wait()
    await player.request_playback(KEXP)
    assert player.play_calls == ["KEXP"]

    attempt.release.set()
    await player.wait_for_playback_idle()

    assert player.station == KEXP
    assert player.requested_call_sign is None


@async_test
async def test_failed_playback_clears_pending_without_confirming():
    attempt = PlaybackAttempt(success=False)
    player = ControlledPlayer([attempt])

    await player.request_playback(KEXP)
    await attempt.started.wait()
    attempt.release.set()
    await player.wait_for_playback_idle()

    assert player.station is None
    assert player.requested_call_sign is None
    assert player.failed_call_sign == "KEXP"

    retry = PlaybackAttempt()
    player.attempts.append(retry)
    await player.request_playback(KEXP)
    assert player.failed_call_sign is None
    retry.release.set()
    await player.wait_for_playback_idle()


@async_test
async def test_latest_request_cancels_and_replaces_slow_request():
    slow = PlaybackAttempt()
    latest = PlaybackAttempt()
    player = ControlledPlayer([slow, latest])

    await player.request_playback(KEXP)
    await slow.started.wait()
    await player.request_playback(KGUT)
    await latest.started.wait()

    assert slow.cancelled
    assert player.requested_call_sign == "KGUT"

    latest.release.set()
    await player.wait_for_playback_idle()
    assert player.station == KGUT
    assert player.play_calls == ["KEXP", "KGUT"]


@async_test
async def test_stop_cancels_pending_request_and_clears_state():
    attempt = PlaybackAttempt()
    player = ControlledPlayer([attempt])

    await player.request_playback(KEXP)
    await attempt.started.wait()
    await player.request_stop()
    await player.wait_for_playback_idle()

    assert attempt.cancelled
    assert player.station is None
    assert player.requested_call_sign is None


@async_test
async def test_idle_waits_for_terminal_state_broadcast():
    attempt = PlaybackAttempt()
    player = ControlledPlayer([attempt])
    terminal_started = asyncio.Event()
    release_terminal = asyncio.Event()

    async def send(message):
        if json.loads(message)["data"] == {
            "call_sign": "KEXP",
            "requested_call_sign": None,
            "failed_call_sign": None,
        }:
            terminal_started.set()
            await release_terminal.wait()

    player.register_client(SimpleNamespace(_send=send))

    await player.request_playback(KEXP)
    await attempt.started.wait()
    attempt.release.set()
    await terminal_started.wait()

    wait = asyncio.create_task(player.wait_for_playback_idle())
    await asyncio.sleep(0)
    assert not wait.done()

    release_terminal.set()
    await wait
