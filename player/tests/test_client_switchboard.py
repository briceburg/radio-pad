import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, Mock

from lib.client_switchboard import SwitchboardClient
from lib.interfaces import RadioPadPlayer, RadioPadPlayerConfig


def test_switchboard_identifies_loaded_radio_dial_revision():
    config = RadioPadPlayerConfig(
        radio_dial_url="https://registry.example/radio-dial",
        radio_dial_revision='"v1"',
        stations=[],
    )
    player = cast(
        RadioPadPlayer,
        SimpleNamespace(config=config),
    )

    client = SwitchboardClient(player)

    assert client.http_headers["RadioPad-Radio-Dial-Url"] == config.radio_dial_url
    assert client.http_headers["RadioPad-Radio-Dial-Revision"] == '"v1"'


def test_switchboard_reloads_new_radio_dial_revision():
    config = RadioPadPlayerConfig(
        radio_dial_url="https://registry.example/radio-dial",
        radio_dial_revision='"v1"',
        stations=[],
    )
    player_state = SimpleNamespace(config=config)
    reload_config = Mock(side_effect=lambda value: setattr(player_state, "config", value))
    player_state.update_config = reload_config
    player = cast(RadioPadPlayer, player_state)
    refreshed = RadioPadPlayerConfig(
        radio_dial_url=config.radio_dial_url,
        radio_dial_revision='"v2"',
        stations=[],
    )

    async def reload(url, revision):
        player.update_config(refreshed)

    reload_radio_dial = AsyncMock(side_effect=reload)
    client = SwitchboardClient(player, radio_dial_reloader=reload_radio_dial)

    async def handle_and_settle():
        await client.handle_event(
            {
                "event": "radio_dial_state",
                "data": {"url": config.radio_dial_url, "revision": '"v2"'},
            }
        )
        assert client._radio_dial_task is not None
        await client._radio_dial_task

    asyncio.run(handle_and_settle())

    reload_radio_dial.assert_awaited_once_with(config.radio_dial_url, '"v2"')
    reload_config.assert_called_once_with(refreshed)
    assert client.http_headers["RadioPad-Radio-Dial-Revision"] == '"v2"'
