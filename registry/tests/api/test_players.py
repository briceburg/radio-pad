from http import HTTPStatus

import pytest
from starlette.testclient import TestClient

from api.models.pagination import PaginationParams
from datastore.types import JsonDoc
from models.player import PlayerCreate
from tests.api._helpers import (
    INVALID_SLUGS,
    VALID_ACCOUNT_ITEM_SLUG_PAIRS,
    assert_item_fields,
)
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


def test_get_player_not_found(player_api: PlayerApi) -> None:
    player_api.get("testuser1", "does-not-exist", expected_status=404)


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


@pytest.mark.parametrize("invalid_id", INVALID_SLUGS)
def test_player_invalid_id_rejected(client: TestClient, invalid_id: str) -> None:
    resp = client.put(
        f"/v1/accounts/testuser1/players/{invalid_id}",
        json={"name": "Bad"},
    )
    assert resp.status_code == 422


# New: invalid account_id path segment should 422 before hitting model logic
@pytest.mark.parametrize("invalid_account_id", INVALID_SLUGS)
def test_player_invalid_account_id_rejected(client: TestClient, invalid_account_id: str) -> None:
    resp = client.put(
        f"/v1/accounts/{invalid_account_id}/players/playerx",
        json={"name": "X"},
    )
    assert resp.status_code == 422


# Positive edge-case slugs should work
@pytest.mark.parametrize("account_id,player_id", VALID_ACCOUNT_ITEM_SLUG_PAIRS)
def test_player_valid_slug_edge_cases(client: TestClient, account_id: str, player_id: str) -> None:
    resp = client.put(
        f"/v1/accounts/{account_id}/players/{player_id}",
        json={"name": "Edge"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == player_id
    assert data["account_id"] == account_id


def test_error_detail_shape_for_not_found(client: TestClient) -> None:
    # Non-existent player
    r = client.get("/v1/accounts/testuser1/players/missing-player")
    assert r.status_code == HTTPStatus.NOT_FOUND
    body = r.json()
    assert body["code"] == "not_found"
    assert body["details"]["player_id"] == "missing-player"


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


# --- Pagination Tests ---


def test_pagination_out_of_bounds(player_api: PlayerApi) -> None:
    data = player_api.list("testuser1", params=PaginationParams(page=1000, per_page=1))
    assert len(data["items"]) == 0


def test_per_page_and_link_behavior_single_page(player_api: PlayerApi) -> None:
    data = player_api.list("testuser1", params=PaginationParams(page=1, per_page=5))
    assert len(data["items"]) == 2


def test_pagination_works(player_api: PlayerApi) -> None:
    data = player_api.list("testuser1", params=PaginationParams(page=1, per_page=1))
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "player1"

    data = player_api.list("testuser1", params=PaginationParams(page=2, per_page=1))
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == "player2"
