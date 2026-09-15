import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call, patch

import pytest

from lib.exceptions import ConfigError
from lib.interfaces import RadioPadPlayerConfig, RadioPadStation
from player import _reload_radio_dial


def player_config(*stations, revision='"v1"'):
    return RadioPadPlayerConfig(
        radio_dial_url="https://registry.example.test/radio-dial",
        radio_dial_revision=revision,
        switchboard_url="wss://switchboard.example.test/player",
        stations=[RadioPadStation(call_sign, stream_url) for call_sign, stream_url in stations],
    )


def fake_player(config):
    return SimpleNamespace(config=config, update_config=Mock())


def fake_macropad():
    return SimpleNamespace(publish_station_menu=AsyncMock(), publish_status=AsyncMock())


@pytest.mark.parametrize("stations_changed", [True, False], ids=("stations", "metadata"))
def test_reload_updates_revision_and_only_pushes_changed_station_menu(stations_changed):
    current = player_config(("KEXP", "https://example.test/old"))
    stream_url = "https://example.test/new" if stations_changed else "https://example.test/old"
    refreshed = player_config(("KEXP", stream_url), revision='"v2"')
    player = fake_player(current)
    macropad = fake_macropad()

    with patch("player.config.load_radio_dial", AsyncMock(return_value=refreshed)) as load:
        asyncio.run(_reload_radio_dial(player, macropad, current.radio_dial_url, '"v2"'))

    load.assert_awaited_once_with(current.radio_dial_url, current.switchboard_url)
    player.update_config.assert_called_once_with(refreshed)
    if stations_changed:
        macropad.publish_station_menu.assert_awaited_once_with()
    else:
        macropad.publish_station_menu.assert_not_awaited()
    macropad.publish_status.assert_awaited_once_with("radio_dial", "ok", None)


def test_reload_retries_transient_failure():
    current = player_config(("KEXP", "https://example.test/old"))
    refreshed = player_config(("KEXP", "https://example.test/new"), revision='"v2"')
    player = fake_player(current)
    macropad = fake_macropad()
    load = AsyncMock(
        side_effect=[
            ConfigError("unavailable", status_summary="RadioDial unavailable"),
            refreshed,
        ]
    )

    with (
        patch("player.config.load_radio_dial", load),
        patch("player.asyncio.sleep", AsyncMock()) as sleep,
    ):
        asyncio.run(_reload_radio_dial(player, macropad, current.radio_dial_url, '"v2"'))

    sleep.assert_awaited_once()
    assert macropad.publish_status.await_args_list == [
        call("radio_dial", "warning", "RadioDial unavailable"),
        call("radio_dial", "ok", None),
    ]
