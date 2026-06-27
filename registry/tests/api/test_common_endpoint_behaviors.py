from http import HTTPStatus
from typing import cast

import pytest
from starlette.testclient import TestClient

from datastore.types import JsonDoc
from tests.api._helpers import INVALID_SLUGS, VALID_ACCOUNT_ITEM_SLUG_PAIRS, assert_pagination_page


def _put_ok(client: TestClient, path: str, payload: JsonDoc) -> JsonDoc:
    response = client.put(path, json=payload)
    assert response.status_code == HTTPStatus.OK, response.text
    return cast(JsonDoc, response.json())


@pytest.mark.parametrize(
    "path_template,payload",
    [
        ("accounts/{value}", {"name": "Bad"}),
        ("accounts/testuser1/players/{value}", {"name": "Bad"}),
        ("accounts/testuser1/radio-dials/{value}", {"name": "Bad", "stations": []}),
    ],
    ids=["account", "player", "radio-dial"],
)
@pytest.mark.parametrize("invalid_value", INVALID_SLUGS)
def test_invalid_object_ids_are_rejected(
    client: TestClient,
    path_template: str,
    payload: JsonDoc,
    invalid_value: str,
) -> None:
    response = client.put(path_template.format(value=invalid_value), json=payload)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize(
    "path_template,payload",
    [
        ("accounts/{value}/players/playerx", {"name": "Bad"}),
        ("accounts/{value}/stations/WXYZ", {"stream_url": "https://example.com/stream"}),
        ("accounts/{value}/radio-dials/dialx", {"name": "Bad", "stations": []}),
    ],
    ids=["player", "station", "radio-dial"],
)
@pytest.mark.parametrize("invalid_value", INVALID_SLUGS)
def test_invalid_account_ids_are_rejected(
    client: TestClient,
    path_template: str,
    payload: JsonDoc,
    invalid_value: str,
) -> None:
    response = client.put(path_template.format(value=invalid_value), json=payload)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("account_id,object_id", VALID_ACCOUNT_ITEM_SLUG_PAIRS)
@pytest.mark.parametrize(
    "path_template,payload,identity_field",
    [
        ("accounts/{account_id}/players/{object_id}", {"name": "Edge"}, "id"),
        ("accounts/{account_id}/radio-dials/{object_id}", {"name": "Edge", "stations": []}, "key"),
    ],
    ids=["player", "radio-dial"],
)
def test_account_scoped_valid_slug_edges(
    client: TestClient,
    account_id: str,
    object_id: str,
    path_template: str,
    payload: JsonDoc,
    identity_field: str,
) -> None:
    data = _put_ok(client, path_template.format(account_id=account_id, object_id=object_id), payload)
    expected_identity = object_id if identity_field == "id" else f"{account_id}/{object_id}"
    assert data[identity_field] == expected_identity


@pytest.mark.parametrize(
    "path,expected_details",
    [
        ("accounts/missing-account", {"account_id": "missing-account"}),
        (
            "accounts/testuser1/players/missing-player",
            {"account_id": "testuser1", "player_id": "missing-player"},
        ),
        (
            "accounts/testuser1/stations/NOPE",
            {"account_id": "testuser1", "call_sign": "NOPE"},
        ),
        (
            "accounts/testuser1/radio-dials/missing-dial",
            {"account_id": "testuser1", "radio_dial_id": "missing-dial"},
        ),
    ],
    ids=["account", "player", "station", "radio-dial"],
)
def test_not_found_error_shape(client: TestClient, path: str, expected_details: dict[str, str]) -> None:
    response = client.get(path)

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["details"] == expected_details


@pytest.mark.parametrize(
    "path,payload",
    [
        ("accounts/spec-boundary", {"id": "other", "name": "Account"}),
        ("accounts/testuser1/players/spec-boundary", {"account_id": "other", "name": "Player"}),
        (
            "accounts/testuser1/stations/WXYZ",
            {"call_sign": "OTHER", "stream_url": "https://example.com/stream"},
        ),
        (
            "accounts/testuser1/radio-dials/spec-boundary",
            {"key": "other/dial", "name": "RadioDial", "stations": []},
        ),
    ],
    ids=["account", "player", "station", "radio-dial"],
)
def test_specs_reject_path_derived_identity(client: TestClient, path: str, payload: JsonDoc) -> None:
    assert client.put(path, json=payload).status_code == HTTPStatus.UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("resource", ["accounts", "players"])
def test_pagination_behavior_is_consistent(client: TestClient, resource: str) -> None:
    if resource == "accounts":
        list_path = "accounts"
        item_ids = ["community", "testuser1"]
    else:
        list_path = "accounts/testuser1/players"
        item_ids = ["player1", "player2"]

    response = client.get(list_path, params={"page": 1, "per_page": 1})
    assert response.status_code == HTTPStatus.OK
    assert_pagination_page(
        response.json(),
        item_ids=item_ids[:1],
        page=1,
        per_page=1,
        prev=None,
        next="?page=2&per_page=1",
    )

    response = client.get(list_path, params={"page": 2, "per_page": 1})
    assert response.status_code == HTTPStatus.OK
    assert_pagination_page(
        response.json(),
        item_ids=item_ids[1:2],
        page=2,
        per_page=1,
        prev="?page=1&per_page=1",
        next="?page=3&per_page=1",
    )
