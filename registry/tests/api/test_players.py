import pytest
from starlette.testclient import TestClient

from datastore.types import JsonDoc
from models.player import PlayerSpec
from tests.api._helpers import assert_item_fields
from tests.api.client.players import PlayerApi


def test_get_players(player_api: PlayerApi) -> None:
    data = player_api.list("testuser1")
    assert len(data["items"]) == 2


def test_register_player(player_api: PlayerApi) -> None:
    data = player_api.put("testuser1", "test-player", PlayerSpec(name="Test Player"))
    assert_item_fields(data, name="Test Player", radio_dial=None, switchboard_url=None)


def test_register_player_for_new_account(player_api: PlayerApi, client: TestClient) -> None:
    player_api.put("new-account", "test-player", PlayerSpec(name="Test Player"))
    data = player_api.get("new-account", "test-player")
    assert_item_fields(data, name="Test Player")

    # Verify account was created
    accounts_resp = client.get("accounts")
    assert accounts_resp.status_code == 200
    accounts = accounts_resp.json()
    assert "new-account" in [item["id"] for item in accounts["items"]]


def test_update_player(player_api: PlayerApi) -> None:
    player_api.put("testuser1", "player1", PlayerSpec(name="Updated Player"))
    data = player_api.get("testuser1", "player1")
    assert_item_fields(data, name="Updated Player")


def test_player_put_replaces_optional_configuration(player_api: PlayerApi) -> None:
    player_api.put(
        "testuser1",
        "player1",
        PlayerSpec(
            name="Original",
            radio_dial="community/briceburg",
            switchboard_url="wss://switch.example.com/custom",
        ),
    )

    player = player_api.put("testuser1", "player1", PlayerSpec(name="Replaced"))

    assert_item_fields(player, name="Replaced", radio_dial=None, switchboard_url=None)
    assert player_api.get("testuser1", "player1") == player


def test_player_rejects_missing_radio_dial(client: TestClient) -> None:
    response = client.put(
        "accounts/testuser1/players/missing-dial",
        json={"name": "Missing", "radio_dial": "community/missing"},
    )

    assert response.status_code == 404
    assert response.json()["details"] == {"radio_dial": "community/missing"}


@pytest.mark.parametrize(
    "body,expect_status",
    [
        (PlayerSpec.model_validate({"name": "Valid Player"}), 200),
        ({}, 422),  # missing required name
    ],
)
def test_player_create_validation(client: TestClient, body: PlayerSpec | JsonDoc, expect_status: int) -> None:
    payload = body if isinstance(body, dict) else body.model_dump(mode="json")
    resp = client.put("accounts/testuser1/players/param-player", json=payload)
    assert resp.status_code == expect_status
    if expect_status == 200:
        assert isinstance(body, PlayerSpec)
        assert resp.json()["name"] == body.name
    else:
        assert resp.json()["detail"]
