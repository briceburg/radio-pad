from http import HTTPStatus
from typing import cast

import pytest
from starlette.testclient import TestClient

from datastore.types import JsonDoc
from tests.api._helpers import (
    INVALID_SLUGS,
    VALID_ACCOUNT_ITEM_SLUG_PAIRS,
    VALID_SLUG_EDGE_CASES,
    assert_item_fields,
    assert_pagination_page,
)


def _put_ok(client: TestClient, path: str, payload: JsonDoc) -> JsonDoc:
    response = client.put(path, json=payload)
    assert response.status_code == HTTPStatus.OK, response.text
    return cast(JsonDoc, response.json())


def _assert_not_found(
    client: TestClient,
    *,
    path: str,
    expected_details: dict[str, str],
) -> None:
    response = client.get(path)
    assert response.status_code == HTTPStatus.NOT_FOUND
    body = response.json()
    assert body["code"] == "not_found"
    assert body["message"]
    assert body["details"] == expected_details


@pytest.mark.parametrize(
    "path_template,payload",
    [
        ("/accounts/{value}", {"name": "Bad"}),
        ("/accounts/testuser1/players/{value}", {"name": "Bad"}),
        ("/presets/{value}", {"name": "Bad", "stations": []}),
        ("/accounts/testuser/presets/{value}", {"name": "Bad", "stations": []}),
    ],
    ids=["account-id", "player-id", "global-preset-id", "account-preset-id"],
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
        ("/accounts/{value}/players/playerx", {"name": "Bad"}),
        ("/accounts/{value}/presets/presetx", {"name": "Bad", "stations": []}),
    ],
    ids=["player-account-id", "account-preset-account-id"],
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


@pytest.mark.parametrize("preset_id", VALID_SLUG_EDGE_CASES)
def test_global_preset_valid_slug_edge_cases(client: TestClient, preset_id: str) -> None:
    data = _put_ok(client, f"/presets/{preset_id}", {"name": "Edge", "stations": []})
    assert_item_fields(data, id=preset_id)


@pytest.mark.parametrize("account_id,object_id", VALID_ACCOUNT_ITEM_SLUG_PAIRS)
@pytest.mark.parametrize(
    "path_template,payload",
    [
        ("/accounts/{account_id}/players/{object_id}", {"name": "Edge"}),
        ("/accounts/{account_id}/presets/{object_id}", {"name": "Edge", "stations": []}),
    ],
    ids=["player", "account-preset"],
)
def test_account_scoped_valid_slug_edge_cases(
    client: TestClient,
    account_id: str,
    object_id: str,
    path_template: str,
    payload: JsonDoc,
) -> None:
    data = _put_ok(client, path_template.format(account_id=account_id, object_id=object_id), payload)
    assert_item_fields(data, id=object_id, account_id=account_id)


@pytest.mark.parametrize(
    "path,expected_details",
    [
        ("/accounts/missing-account", {"account_id": "missing-account"}),
        (
            "/accounts/testuser1/players/missing-player",
            {"account_id": "testuser1", "player_id": "missing-player"},
        ),
        ("/presets/missing-preset", {"preset_id": "missing-preset"}),
        (
            "/accounts/testuser/presets/missing-preset",
            {"account_id": "testuser", "preset_id": "missing-preset"},
        ),
    ],
    ids=["account", "player", "global-preset", "account-preset"],
)
def test_not_found_error_shape(client: TestClient, path: str, expected_details: dict[str, str]) -> None:
    _assert_not_found(client, path=path, expected_details=expected_details)


@pytest.mark.parametrize("resource", ["player", "global-preset", "account-preset"])
def test_partial_update_preserves_existing_fields(client: TestClient, resource: str) -> None:
    initial: JsonDoc
    update: JsonDoc
    expected: JsonDoc

    if resource == "player":
        create_path = fetch_path = "/accounts/testuser1/players/player1"
        initial = {
            "name": "Original",
            "stations_url": "https://example.com/custom.json",
            "switchboard_url": "wss://switch.example.com/custom",
        }
        update = {"name": "Renamed"}
        expected = {
            "name": "Renamed",
            "stations_url": "https://example.com/custom.json",
            "switchboard_url": "wss://switch.example.com/custom",
        }
    elif resource == "global-preset":
        create_path = fetch_path = "/presets/partial"
        initial = {
            "name": "Original",
            "category": "Music",
            "description": "Desc",
            "stations": [{"name": "A", "url": "https://a.com"}],
        }
        update = {"name": "Renamed", "stations": []}
        expected = {"name": "Renamed", "category": "Music", "description": "Desc"}
    else:
        create_path = fetch_path = "/accounts/testuser/presets/partial"
        initial = {
            "name": "Original",
            "category": "Music",
            "description": "Desc",
            "stations": [{"name": "A", "url": "https://a.com"}],
        }
        update = {"name": "Renamed", "stations": [{"name": "A", "url": "https://a.com"}]}
        expected = {"account_id": "testuser", "name": "Renamed", "category": "Music", "description": "Desc"}

    created = _put_ok(client, create_path, initial)
    updated = _put_ok(client, create_path, update)
    fetched = client.get(fetch_path)
    assert fetched.status_code == HTTPStatus.OK

    assert_item_fields(created, **{k: v for k, v in expected.items() if k != "name"}, name="Original")
    assert_item_fields(updated, **expected)
    assert_item_fields(cast(JsonDoc, fetched.json()), **expected)


@pytest.mark.parametrize("resource", ["accounts", "players", "global-presets"])
def test_pagination_behavior_is_consistent(client: TestClient, resource: str) -> None:
    if resource == "accounts":
        list_path = "/accounts"
        single_page_ids = ["testuser1", "testuser2"]
        first_page_ids = ["testuser1"]
        second_page_ids = ["testuser2"]
    elif resource == "players":
        list_path = "/accounts/testuser1/players"
        single_page_ids = ["player1", "player2"]
        first_page_ids = ["player1"]
        second_page_ids = ["player2"]
    else:
        list_path = "/presets"
        _put_ok(client, "/presets/second-preset", {"name": "Second", "stations": []})
        single_page_ids = ["briceburg", "second-preset"]
        first_page_ids = ["briceburg"]
        second_page_ids = ["second-preset"]

    response = client.get(list_path, params={"page": 1000, "per_page": 1})
    assert response.status_code == HTTPStatus.OK
    assert_pagination_page(
        response.json(),
        item_ids=[],
        page=1000,
        per_page=1,
        prev="?page=999&per_page=1",
        next=None,
    )

    response = client.get(list_path, params={"page": 1, "per_page": 5})
    assert response.status_code == HTTPStatus.OK
    assert_pagination_page(
        response.json(),
        item_ids=single_page_ids,
        page=1,
        per_page=5,
        prev=None,
        next=None,
    )

    response = client.get(list_path, params={"page": 1, "per_page": 1})
    assert response.status_code == HTTPStatus.OK
    assert_pagination_page(
        response.json(),
        item_ids=first_page_ids,
        page=1,
        per_page=1,
        prev=None,
        next="?page=2&per_page=1",
    )

    response = client.get(list_path, params={"page": 2, "per_page": 1})
    assert response.status_code == HTTPStatus.OK
    assert_pagination_page(
        response.json(),
        item_ids=second_page_ids,
        page=2,
        per_page=1,
        prev="?page=1&per_page=1",
        next="?page=3&per_page=1",
    )
