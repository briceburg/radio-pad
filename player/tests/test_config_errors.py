import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import lib.config as config
from lib.exceptions import ConfigError


def assert_config_error_status(coro, expected_status):
    with pytest.raises(ConfigError) as error:
        asyncio.run(coro)
    assert error.value.status_summary == expected_status


def test_missing_radio_dial_url_reports_config_error():
    assert_config_error_status(
        config.make(
            player="briceburg/living-room",
            registry_url="https://registry.example.test/api",
            enable_discovery=False,
        ),
        "RadioDial config error",
    )


def test_invalid_player_id_reports_player_config_error():
    assert_config_error_status(
        config.make(
            player="living-room",
            registry_url="https://registry.example.test/api",
        ),
        "Player config error",
    )


def test_unclassified_config_error_defaults_to_registry_unavailable():
    assert ConfigError("unclassified").status_summary == "Registry unavailable"


def test_unavailable_radio_dial_reports_unavailable():
    with patch("lib.config.fetch_json_url", AsyncMock(return_value=None)):
        assert_config_error_status(
            config.make(
                player="briceburg/living-room",
                registry_url="https://registry.example.test/api",
                radio_dial_url="https://registry.example.test/radio-dial",
                enable_discovery=False,
            ),
            "RadioDial unavailable",
        )


@pytest.mark.parametrize(
    "radio_dial",
    [
        {"stations": "invalid"},
        {"stations": [None]},
        {"stations": [{"call_sign": "KEXP"}]},
        {"stations": [{"call_sign": "", "stream_url": "https://example.test"}]},
        {"stations": [{"call_sign": "KEXP", "stream_url": ""}]},
        {
            "stations": [
                {"call_sign": "KEXP", "stream_url": "https://example.test/one"},
                {"call_sign": "KEXP", "stream_url": "https://example.test/two"},
            ]
        },
    ],
)
def test_malformed_radio_dial_reports_config_error(radio_dial):
    with patch("lib.config.fetch_json_url", AsyncMock(return_value=radio_dial)):
        assert_config_error_status(
            config.make(
                player="briceburg/living-room",
                registry_url="https://registry.example.test/api",
                radio_dial_url="https://registry.example.test/radio-dial",
                enable_discovery=False,
            ),
            "RadioDial config error",
        )
