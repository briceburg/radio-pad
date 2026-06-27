"""Descriptor and slug boundary validation."""

from collections.abc import Callable

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from lib.constants import MAX_DESCRIPTOR_LENGTH
from models import AccountSpec, PlayerSpec, RadioDialSpec, StationSpec


def _assert_descriptor_limit(build_model: Callable[[str], object], field_name: str) -> None:
    valid_value = "a" * MAX_DESCRIPTOR_LENGTH
    invalid_value = valid_value + "a"

    assert getattr(build_model(valid_value), field_name) == valid_value
    with pytest.raises(ValidationError, match=f"String should have at most {MAX_DESCRIPTOR_LENGTH} characters"):
        build_model(invalid_value)


@pytest.mark.parametrize(
    ("build_model", "field_name"),
    [
        (lambda value: AccountSpec(name=value), "name"),
        (lambda value: PlayerSpec(name=value), "name"),
        (lambda value: RadioDialSpec(name=value, stations=[]), "name"),
        (
            lambda value: StationSpec.model_validate(
                {"display_name": value, "stream_url": "https://example.com/stream"}
            ),
            "display_name",
        ),
    ],
    ids=["account", "player", "radio-dial", "station"],
)
def test_descriptor_length_constraint(build_model: Callable[[str], object], field_name: str) -> None:
    _assert_descriptor_limit(build_model, field_name)


def test_slug_id_length_constraint_via_api(client: TestClient) -> None:
    valid_id = "a" * (MAX_DESCRIPTOR_LENGTH - 1) + "1"
    assert client.put(f"accounts/{valid_id}", json={"name": "Test"}).status_code == 200

    invalid_id = valid_id + "1"
    assert client.put(f"accounts/{invalid_id}", json={"name": "Test"}).status_code == 422
