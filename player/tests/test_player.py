import asyncio
import importlib

import pytest

from lib.interfaces import RadioPadClient, RadioPadPlayer, RadioPadPlayerConfig

player_main = importlib.import_module("player")


class DummyPlayer(RadioPadPlayer):
    def __init__(self):
        super().__init__(
            RadioPadPlayerConfig(
                id="briceburg/test-player",
                stations_url="http://example.test/stations.json",
                stations=[],
            )
        )
        self.stop_calls = 0

    async def play(self, station):
        return True

    async def stop(self):
        self.stop_calls += 1
        self.station = None
        return None

    async def volume_up(self):
        return None

    async def volume_down(self):
        return None


class BlockingClient(RadioPadClient):
    def __init__(self, player):
        super().__init__(player)
        self.cancelled = False
        self.closed = False
        self.closed_after_cancel = False

    async def run(self):
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            self.cancelled = True
            raise

    async def _send(self, message):
        return None

    async def close(self):
        self.closed = True
        self.closed_after_cancel = self.cancelled


def test_main_cancels_client_tasks_before_cleanup():
    player = DummyPlayer()
    clients = [BlockingClient(player), BlockingClient(player)]
    for client in clients:
        player.register_client(client)

    async def exercise():
        task = asyncio.create_task(player_main.main(player))
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())

    assert player.stop_calls == 1
    assert all(client.cancelled for client in clients)
    assert all(client.closed for client in clients)
    assert all(client.closed_after_cancel for client in clients)
