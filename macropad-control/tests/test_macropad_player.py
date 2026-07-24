import json

from lib import macropad_player
from lib.macropad_player import (
    PLAYER_SESSION_TIMEOUT_MS,
    STATION_MENU_REQUEST_INTERVAL_MS,
    MacropadPlayer,
)

TICKS_PERIOD = 1 << 29
TICKS_HALF_PERIOD = TICKS_PERIOD // 2


class FakeSerial:
    def __init__(self, incoming=b""):
        self.connected = True
        self.incoming = incoming
        self.writes = []

    @property
    def in_waiting(self):
        return len(self.incoming)

    def write(self, data):
        self.writes.append(data)

    def read(self, amount):
        data = self.incoming[:amount]
        self.incoming = self.incoming[amount:]
        return data


def circuitpython_ticks_diff(new, old):
    return ((new - old + TICKS_HALF_PERIOD) % TICKS_PERIOD) - TICKS_HALF_PERIOD


def written_events(serial):
    return [json.loads(message) for message in b"".join(serial.writes).decode().splitlines()]


def make_player(monkeypatch, now):
    serial = FakeSerial()
    monkeypatch.setattr(macropad_player.usb_cdc, "data", serial)
    monkeypatch.setattr(macropad_player, "ticks_ms", lambda: now[0])
    monkeypatch.setattr(macropad_player, "ticks_diff", circuitpython_ticks_diff)
    monkeypatch.setattr(macropad_player.time, "sleep", lambda _seconds: None)
    return MacropadPlayer(), serial


def test_first_station_menu_request_is_immediate_during_negative_tick_phase(monkeypatch):
    now = [TICKS_HALF_PERIOD + STATION_MENU_REQUEST_INTERVAL_MS]
    player, serial = make_player(monkeypatch, now)

    player.request_station_menu()

    assert written_events(serial) == [{"event": "station_menu_request", "data": None}]


def test_station_menu_requests_remain_throttled_across_tick_wrap(monkeypatch):
    now = [TICKS_PERIOD - 1000]
    player, serial = make_player(monkeypatch, now)

    player.request_station_menu()
    now[0] = 1000
    player.request_station_menu()
    now[0] = STATION_MENU_REQUEST_INTERVAL_MS - 1000
    player.request_station_menu()

    assert written_events(serial) == [
        {"event": "station_menu_request", "data": None},
        {"event": "station_menu_request", "data": None},
    ]


def test_reconnect_allows_immediate_station_menu_request(monkeypatch):
    now = [TICKS_HALF_PERIOD + STATION_MENU_REQUEST_INTERVAL_MS]
    player, serial = make_player(monkeypatch, now)
    player.request_station_menu()

    serial.connected = False
    assert not player.connected
    serial.connected = True
    player.request_station_menu()

    assert written_events(serial) == [
        {"event": "station_menu_request", "data": None},
        {"event": "station_menu_request", "data": None},
    ]


def test_connection_at_tick_zero_can_become_stale(monkeypatch):
    now = [0]
    player, _serial = make_player(monkeypatch, now)
    assert player.connected

    now[0] = PLAYER_SESSION_TIMEOUT_MS + 1

    assert player.session_stale


def test_flush_buffer_discards_blank_lines_and_queued_events(monkeypatch):
    player, serial = make_player(monkeypatch, [0])
    serial.incoming = b'\n{"event": "station_menu_request", "data": null}\n'
    player._serial_buffer = '{"event": "volume_up", "data": null}\n'

    player.flush_buffer()

    assert serial.in_waiting == 0
    assert player.read_event() is None
