from http import HTTPStatus

import pytest
from starlette.testclient import TestClient

from datastore.types import JsonDoc
from models.player import PlayerCreate
from tests.api._helpers import assert_item_fields
from tests.api.client.players import PlayerApi


def test_get_players(player_api: PlayerApi) -> None:
    data = player_api.list("testuser1")
    assert len(data["items"]) == 2


def test_register_player(player_api: PlayerApi) -> None:
    data = player_api.put("testuser1", "test-player", PlayerCreate.model_validate({"name": "Test Player"}))
    assert_item_fields(data, name="Test Player")
    assert "stations_url" in data


def test_register_player_for_new_account(player_api: PlayerApi, client: TestClient) -> None:
    player_api.put("new-account", "test-player", PlayerCreate.model_validate({"name": "Test Player"}))
    data = player_api.get("new-account", "test-player")
    assert_item_fields(data, name="Test Player")

    # Verify account was created
    accounts_resp = client.get("/v1/accounts")
    assert accounts_resp.status_code == 200
    accounts = accounts_resp.json()
    assert "new-account" in [item["id"] for item in accounts["items"]]


def test_update_player(player_api: PlayerApi) -> None:
    player_api.put("testuser1", "player1", PlayerCreate.model_validate({"name": "Updated Player"}))
    data = player_api.get("testuser1", "player1")
    assert_item_fields(data, name="Updated Player")


@pytest.mark.parametrize(
    "initial",
    [
        PlayerCreate.model_validate({"name": "Original Name", "stations_url": "https://example.com/custom.json"}),
        PlayerCreate.model_validate({"name": "Original Name", "switchboard_url": "wss://switch.example.com/custom"}),
        PlayerCreate.model_validate(
            {
                "name": "Original Name",
                "stations_url": "https://example.com/custom.json",
                "switchboard_url": "wss://switch.example.com/custom",
            }
        ),
    ],
)
def test_player_partial_update_preserves_existing_data(player_api: PlayerApi, initial: PlayerCreate) -> None:
    account_id = "testuser1"
    player_id = "player1"
    # Seed optional fields on existing player
    player_api.put(account_id, player_id, initial)
    # Now update only the name
    put_data = player_api.put(account_id, player_id, PlayerCreate.model_validate({"name": "Updated Player Name"}))
    assert_item_fields(
        put_data, name="Updated Player Name", **initial.model_dump(mode="json", exclude_none=True, exclude={"name"})
    )
    # Fetch again to ensure persistence
    get_data = player_api.get(account_id, player_id)
    assert_item_fields(
        get_data, name="Updated Player Name", **initial.model_dump(mode="json", exclude_none=True, exclude={"name"})
    )


@pytest.mark.parametrize(
    "body,expect_status",
    [
        (PlayerCreate.model_validate({"name": "Valid Player"}), 200),
        ({}, 422),  # missing required name
    ],
)
def test_player_create_validation(client: TestClient, body: PlayerCreate | JsonDoc, expect_status: int) -> None:
    payload = body if isinstance(body, dict) else body.model_dump(mode="json")
    resp = client.put("/v1/accounts/testuser1/players/param-player", json=payload)
    assert resp.status_code == expect_status
    if expect_status == 200:
        assert isinstance(body, PlayerCreate)
        assert resp.json()["name"] == body.name
    else:
        assert resp.json()["detail"]


def test_conflict_error_shape_and_status(client: TestClient) -> None:
    # Create a player
    r = client.put(
        "/v1/accounts/testuser1/players/p1",
        json=PlayerCreate.model_validate({"name": "P"}).model_dump(exclude_none=True),
    )
    assert r.status_code == HTTPStatus.OK

    # Try a quick subsequent write. If a conflict occurs, validate error shape.
    r2 = client.put("/v1/accounts/testuser1/players/p1", json={"name": "P2"})
    if r2.status_code == HTTPStatus.CONFLICT:
        body = r2.json()
        assert body["code"] == "conflict"
        assert "message" in body
