import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import lib.config as config
from lib.exceptions import ConfigError


def assert_config_error_status(coro, expected_status):
    with pytest.raises(ConfigError) as error:
        asyncio.run(coro)
    assert error.value.status_summary == expected_status


def test_missing_station_url_reports_station_config_error():
    assert_config_error_status(
        config.make(
            player="briceburg/living-room",
            registry_url="https://registry.example.test/api",
            enable_discovery=False,
        ),
        "Station config error",
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


def test_unavailable_station_preset_reports_station_unavailable():
    with patch("lib.config.fetch_json_url", AsyncMock(return_value=None)):
        assert_config_error_status(
            config.make(
                player="briceburg/living-room",
                registry_url="https://registry.example.test/api",
                stations_url="https://stations.example.test/preset.json",
                enable_discovery=False,
            ),
            "Stations unavailable",
        )
