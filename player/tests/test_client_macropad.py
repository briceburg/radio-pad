import asyncio
import json
from types import SimpleNamespace

from lib.client_macropad import MacropadClient
from lib.interfaces import RadioPadPlayer, RadioPadPlayerConfig


class DummyPlayer(RadioPadPlayer):
    async def play(self, station):
        return True

    async def stop(self):
        return None

    async def volume_up(self):
        return None

    async def volume_down(self):
        return None


def make_player():
    return DummyPlayer(
        RadioPadPlayerConfig(
            id="briceburg/test-player",
            stations_url="http://example.test/stations.json",
            stations=[],
        )
    )


def test_candidate_ports_prefers_explicit_env(monkeypatch):
    client = MacropadClient(make_player())

    monkeypatch.setenv("RADIOPAD_MACROPAD_PORT", "/dev/ttyUSB42")

    assert client._candidate_ports() == ["/dev/ttyUSB42"]


def test_candidate_ports_scans_circuitpython_data_ports(monkeypatch):
    client = MacropadClient(make_player())
    ports = [
        SimpleNamespace(device="/dev/ttyACM0", interface="CircuitPython CDC2"),
        SimpleNamespace(device="/dev/ttyACM1", interface="Debug CDC"),
        SimpleNamespace(device="/dev/ttyACM2", interface=None),
    ]

    monkeypatch.delenv("RADIOPAD_MACROPAD_PORT", raising=False)
    monkeypatch.setattr(
        "lib.client_macropad.serial.tools.list_ports.comports", lambda: ports
    )

    assert client._candidate_ports() == ["/dev/ttyACM0"]


def test_publish_status_sends_sanitized_payload():
    client = MacropadClient(make_player())
    sent_messages = []

    async def fake_send(message):
        sent_messages.append(json.loads(message))

    client.writer = object()
    client._send = fake_send

    asyncio.run(client.publish_status("upstream", None))

    assert sent_messages == [
        {
            "event": "player_status",
            "data": {"scope": "upstream", "summary": ""},
        }
    ]
