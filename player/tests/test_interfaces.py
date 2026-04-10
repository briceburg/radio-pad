import asyncio

from lib.interfaces import (
    RadioPadClient,
    RadioPadPlayer,
    RadioPadPlayerConfig,
    RadioPadStation,
)


class DummyPlayer(RadioPadPlayer):
    def __init__(self, play_result):
        super().__init__(
            RadioPadPlayerConfig(
                id="briceburg/test-player",
                stations_url="http://example.test/stations.json",
                stations=[
                    RadioPadStation(name="WWOZ", url="https://example.test/wwoz")
                ],
            )
        )
        self.play_result = play_result

    async def play(self, station):
        if self.play_result:
            self.station = station
            return True
        self.station = None
        return False

    async def stop(self):
        self.station = None
        return None

    async def volume_up(self):
        return None

    async def volume_down(self):
        return None


class DummyClient(RadioPadClient):
    def __init__(self, player):
        super().__init__(player)
        self.sent_messages = []

    async def run(self):
        return None

    async def _send(self, message):
        self.sent_messages.append(message)

    async def close(self):
        return None


def test_station_request_broadcasts_on_success():
    player = DummyPlayer(play_result=True)
    client = DummyClient(player)
    player.register_client(client)

    asyncio.run(client.handle_event({"event": "station_request", "data": "WWOZ"}))

    assert client.sent_messages == ['{"event": "station_playing", "data": "WWOZ"}']


def test_station_request_skips_broadcast_on_failed_play():
    player = DummyPlayer(play_result=False)
    client = DummyClient(player)
    player.register_client(client)

    asyncio.run(client.handle_event({"event": "station_request", "data": "WWOZ"}))

    assert client.sent_messages == []
