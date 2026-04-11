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


def test_publish_status_sends_scoped_payload():
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


def test_publish_status_string_summary_preserved():
    client = MacropadClient(make_player())
    sent_messages = []

    async def fake_send(message):
        sent_messages.append(json.loads(message))

    client.writer = object()
    client._send = fake_send

    asyncio.run(client.publish_status("playback", "Playback failed"))

    assert sent_messages[0]["data"]["summary"] == "Playback failed"


def test_resend_status_sends_all_scopes():
    client = MacropadClient(make_player())
    sent_messages = []

    async def fake_send(message):
        sent_messages.append(json.loads(message))

    client.writer = object()
    client._send = fake_send
    client._status_by_scope = {"upstream": "Switchboard down", "playback": ""}

    asyncio.run(client.resend_status())

    assert len(sent_messages) == 2
    scopes = {m["data"]["scope"] for m in sent_messages}
    assert scopes == {"upstream", "playback"}
