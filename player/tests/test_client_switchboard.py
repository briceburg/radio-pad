import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from websockets.exceptions import ConnectionClosedError

from lib.client_switchboard import SwitchboardClient
from lib.interfaces import RadioPadPlayer, RadioPadPlayerConfig


@pytest.mark.parametrize("closed_with_error", [False, True], ids=["clean-close", "error-close"])
def test_switchboard_waits_before_reconnecting_and_cancels_promptly(closed_with_error):
    config = RadioPadPlayerConfig(
        radio_dial_url="https://registry.example/radio-dial",
        radio_dial_revision='"v1"',
        switchboard_url="wss://registry.example/switchboard/account/player",
        stations=[],
    )
    player = cast(RadioPadPlayer, SimpleNamespace(config=config, broadcast=AsyncMock()))
    client = SwitchboardClient(player)
    ws = AsyncMock()
    if closed_with_error:
        ws.__aiter__.side_effect = ConnectionClosedError(None, None)

    async def connections(*args, **kwargs):
        yield ws
        pytest.fail("reconnected without a delay")

    with (
        patch("lib.client_switchboard.websockets.connect", side_effect=connections),
        patch("lib.client_switchboard.asyncio.sleep", AsyncMock(side_effect=asyncio.CancelledError)) as sleep,
        pytest.raises(asyncio.CancelledError),
    ):
        asyncio.run(client.run())

    sleep.assert_awaited_once_with(5)
    assert client.ws is None
    assert client._closing


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
    player = cast(RadioPadPlayer, player_state)
    refreshed = RadioPadPlayerConfig(
        radio_dial_url=config.radio_dial_url,
        radio_dial_revision='"v2"',
        stations=[],
    )

    async def reload(url, revision):
        player.config = refreshed

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
    assert player.config is refreshed
    assert client.http_headers["RadioPad-Radio-Dial-Revision"] == '"v2"'
