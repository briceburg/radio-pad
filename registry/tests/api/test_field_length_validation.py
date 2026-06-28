"""Name and identifier boundary validation."""

from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient

from lib.constants import MAX_IDENTIFIER_LENGTH, MAX_NAME_LENGTH
from models import AccountSpec, PlayerSpec, RadioDialSpec


@pytest.mark.parametrize(
    "build_model",
    [
        lambda value: AccountSpec(name=value),
        lambda value: PlayerSpec(name=value),
        lambda value: RadioDialSpec(name=value, stations=[]),
    ],
    ids=["account", "player", "radio-dial"],
)
def test_name_length_constraint(build_model: Callable[[str], Any]) -> None:
    valid_value = "a" * MAX_NAME_LENGTH
    assert build_model(valid_value).name == valid_value

    with pytest.raises(ValidationError, match=f"String should have at most {MAX_NAME_LENGTH} characters"):
        build_model(valid_value + "a")


def test_slug_id_length_constraint_via_api(client: TestClient) -> None:
    valid_id = "a" * (MAX_IDENTIFIER_LENGTH - 1) + "1"
    assert client.put(f"accounts/{valid_id}", json={"name": "Test"}).status_code == 200

    invalid_id = valid_id + "1"
    assert client.put(f"accounts/{invalid_id}", json={"name": "Test"}).status_code == 422
