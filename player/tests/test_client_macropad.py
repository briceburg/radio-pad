import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from lib.client_macropad import MacropadClient, _candidate_ports
from lib.interfaces import RadioPadPlayer, RadioPadPlayerConfig, RadioPadStation


class FakePlayer(RadioPadPlayer):
    def __init__(self):
        self.kexp = RadioPadStation("KEXP", "https://example.test/kexp")
        self.kgut = RadioPadStation("KGUT", "https://example.test/kgut")
        super().__init__(
            RadioPadPlayerConfig(
                id="test-player",
                stations_url="https://example.test/stations",
                stations=[self.kexp, self.kgut],
            )
        )
        self.played = []

    async def play(self, station):
        self.station = station
        self.played.append(station)

    async def stop(self):
        self.station = None

    async def volume_up(self):
        pass

    async def volume_down(self):
        pass


class FakeReader:
    def __init__(self, lines):
        self.lines = iter(lines)

    async def readline(self):
        return next(self.lines, b"")


class FakeWriter:
    def __init__(self):
        self.writes = []
        self.drains = 0
        self.closed = False

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        self.drains += 1

    def close(self):
        self.closed = True

    async def wait_closed(self):
        pass


class FailingWriter(FakeWriter):
    async def drain(self):
        raise ConnectionError("Connection lost")


def write_events(writer):
    return [json.loads(data.decode()) for data in writer.writes]


def test_candidate_ports_prefers_configured_port():
    with patch.dict(
        os.environ, {"RADIOPAD_MACROPAD_PORT": "/dev/macropad"}, clear=True
    ), patch("lib.client_macropad.serial.tools.list_ports.comports") as comports:
        assert _candidate_ports() == ["/dev/macropad"]
        comports.assert_not_called()


def test_candidate_ports_filters_and_sorts_cdc2_ports():
    ports = [
        SimpleNamespace(device="/dev/ttyACM2", interface="CircuitPython CDC2 control"),
        SimpleNamespace(device="/dev/ttyACM0", interface="CircuitPython CDC control"),
        SimpleNamespace(device="/dev/ttyACM1", interface="CircuitPython CDC2 control"),
        SimpleNamespace(device="/dev/ttyUSB0", interface=None),
    ]

    with patch.dict(os.environ, {}, clear=True), patch(
        "lib.client_macropad.serial.tools.list_ports.comports", return_value=ports
    ):
        assert _candidate_ports() == ["/dev/ttyACM1", "/dev/ttyACM2"]


def test_listen_handles_serial_station_request():
    player = FakePlayer()
    client = MacropadClient(player)
    writer = FakeWriter()
    player.register_client(client)
    client.writer = writer
    client.reader = FakeReader([b'{"event":"station_request","data":"KEXP"}\n', b""])

    asyncio.run(client._listen())

    assert player.played == [player.kexp]
    assert write_events(writer) == [{"event": "station_playing", "data": "KEXP"}]
    assert writer.drains == 1


def test_station_list_request_writes_stations_and_current_station():
    player = FakePlayer()
    client = MacropadClient(player)
    writer = FakeWriter()
    player.register_client(client)
    client.writer = writer
    player.station = player.kgut

    asyncio.run(client.handle_message('{"event":"station_list"}'))

    assert write_events(writer) == [
        {"event": "station_list", "data": ["KEXP", "KGUT"]},
        {"event": "station_playing", "data": "KGUT"},
    ]
    assert writer.drains == 2


def test_publish_status_writes_scoped_status_payload():
    player = FakePlayer()
    client = MacropadClient(player)
    writer = FakeWriter()
    client.writer = writer

    asyncio.run(client.publish_status("upstream", "warning", "Switchboard down"))

    assert write_events(writer) == [
        {
            "event": "player_status",
            "data": {
                "scope": "upstream",
                "level": "warning",
                "summary": "Switchboard down",
            },
        }
    ]


def test_station_list_request_replays_status_after_stations():
    player = FakePlayer()
    client = MacropadClient(player)
    writer = FakeWriter()
    player.register_client(client)
    client.writer = writer
    client._status_by_scope = {
        "upstream": {"level": "warning", "summary": "Switchboard down"}
    }

    asyncio.run(client.handle_message('{"event":"station_list"}'))

    assert write_events(writer) == [
        {"event": "station_list", "data": ["KEXP", "KGUT"]},
        {"event": "station_playing", "data": None},
        {
            "event": "player_status",
            "data": {
                "scope": "upstream",
                "level": "warning",
                "summary": "Switchboard down",
            },
        },
    ]


def test_send_drops_lost_macropad_connection_without_raising():
    player = FakePlayer()
    client = MacropadClient(player)
    writer = FailingWriter()
    client.writer = writer

    asyncio.run(client._send('{"event":"player_heartbeat","data":null}'))

    assert writer.closed
    assert client.writer is None
    assert client.reader is None
