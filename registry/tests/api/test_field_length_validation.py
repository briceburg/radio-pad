"""Tests to validate field length constraints are properly enforced."""

from collections.abc import Callable

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from lib.constants import MAX_DESCRIPTOR_LENGTH
from models.account import AccountCreate
from models.player import PlayerCreate
from models.station_preset import AccountStationPresetCreate, GlobalStationPresetCreate

_STATIONS = [{"name": "Test Station", "url": "https://example.com/stream"}]


def _account_with_name(name: str) -> AccountCreate:
    return AccountCreate(name=name)


def _player_with_name(name: str) -> PlayerCreate:
    return PlayerCreate.model_validate({"name": name})


def _global_preset_with_name(name: str) -> GlobalStationPresetCreate:
    return GlobalStationPresetCreate.model_validate({"name": name, "stations": _STATIONS})


def _account_preset_with_name(name: str) -> AccountStationPresetCreate:
    return AccountStationPresetCreate.model_validate({"name": name, "stations": _STATIONS})


def _global_preset_with_category(category: str) -> GlobalStationPresetCreate:
    return GlobalStationPresetCreate.model_validate({"name": "Test", "category": category, "stations": _STATIONS})


def _account_preset_with_category(category: str) -> AccountStationPresetCreate:
    return AccountStationPresetCreate.model_validate({"name": "Test", "category": category, "stations": _STATIONS})


def _assert_descriptor_limit(
    build_model: Callable[[str], object],
    *,
    field_name: str,
    fill: str,
) -> None:
    valid_value = fill * MAX_DESCRIPTOR_LENGTH
    invalid_value = fill * (MAX_DESCRIPTOR_LENGTH + 1)

    model = build_model(valid_value)
    assert getattr(model, field_name) == valid_value

    with pytest.raises(ValidationError, match=f"String should have at most {MAX_DESCRIPTOR_LENGTH} characters"):
        build_model(invalid_value)


class TestFieldLengthValidation:
    """Test that descriptor and slug fields respect MAX_DESCRIPTOR_LENGTH."""

    @pytest.mark.parametrize(
        ("build_model", "field_name"),
        [
            (_account_with_name, "name"),
            (_player_with_name, "name"),
            (_global_preset_with_name, "name"),
            (_account_preset_with_name, "name"),
        ],
        ids=["account-name", "player-name", "global-preset-name", "account-preset-name"],
    )
    def test_name_length_constraint(self, build_model: Callable[[str], object], field_name: str) -> None:
        _assert_descriptor_limit(build_model, field_name=field_name, fill="a")

    @pytest.mark.parametrize(
        "build_model",
        [_global_preset_with_category, _account_preset_with_category],
        ids=["global-preset-category", "account-preset-category"],
    )
    def test_preset_category_length_constraint(self, build_model: Callable[[str], object]) -> None:
        _assert_descriptor_limit(build_model, field_name="category", fill="b")

    def test_slug_id_length_constraint_via_api(self, client: TestClient) -> None:
        valid_id = "a" * (MAX_DESCRIPTOR_LENGTH - 1) + "1"
        resp = client.put(f"/v1/accounts/{valid_id}", json={"name": "Test"})
        assert resp.status_code == 200

        invalid_id = "a" * MAX_DESCRIPTOR_LENGTH + "1"
        resp = client.put(f"/v1/accounts/{invalid_id}", json={"name": "Test"})
        assert resp.status_code == 422
        assert "detail" in resp.json()

    def test_length_constraint_allows_guid_length(self) -> None:
        guid_like_value = "123e4567-e89b-12d3-a456-426614174000"
        assert len(guid_like_value) == MAX_DESCRIPTOR_LENGTH

        assert _account_with_name(guid_like_value).name == guid_like_value
        assert _player_with_name(guid_like_value).name == guid_like_value

        preset = GlobalStationPresetCreate.model_validate(
            {"name": guid_like_value, "category": guid_like_value, "stations": _STATIONS}
        )
        assert preset.name == guid_like_value
        assert preset.category == guid_like_value
