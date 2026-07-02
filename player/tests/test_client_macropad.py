import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from lib.client_macropad import MacropadClient, _candidate_ports
from lib.interfaces import RadioPadPlayer, RadioPadPlayerConfig, RadioPadStation


class FakePlayer(RadioPadPlayer):
    def __init__(self):
        self.kexp = RadioPadStation("KEXP", "https://example.test/kexp")
        self.kgut = RadioPadStation("KGUT", "https://example.test/kgut")
        super().__init__(
            RadioPadPlayerConfig(
                radio_dial_url="https://example.test/radio-dial",
                stations=[self.kexp, self.kgut],
            )
        )
        self.played = []

    async def play(self, station):
        self.station = station
        self.played.append(station)
        return True

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


def client_with_writer(register=False):
    player = FakePlayer()
    client = MacropadClient(player)
    writer = FakeWriter()
    client.writer = writer
    if register:
        player.register_client(client)
    return player, client, writer


def event(name, data=None):
    return {"event": name, "data": data}


def player_status(scope, level, summary=None):
    return event(
        "player_status",
        {"scope": scope, "level": level, "summary": summary},
    )


def written_events(writer):
    return [json.loads(data.decode()) for data in writer.writes]


def test_candidate_ports_prefers_configured_port():
    with (
        patch.dict(os.environ, {"RADIOPAD_MACROPAD_PORT": "/dev/macropad"}, clear=True),
        patch("lib.client_macropad.serial.tools.list_ports.comports") as comports,
    ):
        assert _candidate_ports() == ["/dev/macropad"]
        comports.assert_not_called()


def test_candidate_ports_filters_and_sorts_cdc2_ports():
    ports = [
        SimpleNamespace(device="/dev/ttyACM2", interface="CircuitPython CDC2 control"),
        SimpleNamespace(device="/dev/ttyACM0", interface="CircuitPython CDC control"),
        SimpleNamespace(device="/dev/ttyACM1", interface="CircuitPython CDC2 control"),
        SimpleNamespace(device="/dev/ttyUSB0", interface=None),
    ]

    with (
        patch.dict(os.environ, {}, clear=True),
        patch("lib.client_macropad.serial.tools.list_ports.comports", return_value=ports),
    ):
        assert _candidate_ports() == ["/dev/ttyACM1", "/dev/ttyACM2"]


def test_listen_handles_serial_playback_start():
    player, client, writer = client_with_writer(register=True)
    switchboard = SimpleNamespace(_send=AsyncMock())
    player.register_client(switchboard)
    client.reader = FakeReader([b'{"event":"playback_start","data":{"call_sign":"KEXP"}}\n', b""])

    async def listen_and_settle():
        await client._listen()
        await player.wait_for_playback_idle()

    asyncio.run(listen_and_settle())

    expected = [
        event("playback_state", {"call_sign": None, "requested_call_sign": "KEXP"}),
        event("playback_state", {"call_sign": "KEXP", "requested_call_sign": None}),
    ]
    assert player.played == [player.kexp]
    assert written_events(writer) == expected
    assert [json.loads(call.args[0]) for call in switchboard._send.await_args_list] == expected
    assert writer.drains == 2


def test_station_menu_request_writes_call_signs_and_current_station():
    player, client, writer = client_with_writer(register=True)
    player.station = player.kgut

    asyncio.run(client.handle_message('{"event":"station_menu_request"}'))

    assert written_events(writer) == [
        event("station_menu", ["KEXP", "KGUT"]),
        event("playback_state", {"call_sign": "KGUT", "requested_call_sign": None}),
    ]
    assert writer.drains == 2


def test_publish_status_writes_scoped_status_payload():
    _, client, writer = client_with_writer(register=True)

    asyncio.run(client.publish_status("switchboard", "warning", "Switchboard down"))

    assert written_events(writer) == [player_status("switchboard", "warning", "Switchboard down")]


def test_publish_ok_status_clears_retained_status_after_sending():
    _, client, writer = client_with_writer(register=True)
    asyncio.run(client.publish_status("switchboard", "warning", "Switchboard down"))
    writer.writes.clear()

    asyncio.run(client.publish_status("switchboard", "ok"))
    assert written_events(writer) == [player_status("switchboard", "ok")]

    writer.writes.clear()
    asyncio.run(client.resend_status())

    assert written_events(writer) == []


def test_station_menu_request_replays_status_after_stations():
    _, client, writer = client_with_writer(register=True)
    asyncio.run(client.publish_status("switchboard", "warning", "Switchboard down"))
    writer.writes.clear()

    asyncio.run(client.handle_message('{"event":"station_menu_request"}'))

    assert written_events(writer) == [
        event("station_menu", ["KEXP", "KGUT"]),
        event("playback_state", {"call_sign": None, "requested_call_sign": None}),
        player_status("switchboard", "warning", "Switchboard down"),
    ]


def test_invalid_call_sign_reports_failure_without_replacing_playback():
    player, client, writer = client_with_writer(register=True)
    statuses = []

    async def report(level, summary):
        statuses.append((level, summary))

    player.status_reporter = report
    player.station = player.kexp

    asyncio.run(client.handle_message('{"event":"playback_start","data":{"call_sign":"NOPE"}}'))

    assert statuses == [("error", "Station NOPE unavailable")]
    assert written_events(writer) == [event("playback_state", {"call_sign": "KEXP", "requested_call_sign": None})]


def test_send_drops_lost_macropad_connection_without_raising():
    player = FakePlayer()
    client = MacropadClient(player)
    writer = FailingWriter()
    client.writer = writer

    asyncio.run(client._send('{"event":"player_heartbeat","data":null}'))

    assert writer.closed
    assert client.writer is None
    assert client.reader is None
