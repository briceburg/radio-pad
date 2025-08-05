def test_get_players(client):
    response = client.get("/v1/players/testuser1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert data["total"] == 2
    assert isinstance(data["items"], list)


def test_get_players_invalid_data_returns_500(client, mock_store):
    mock_store._players = {"testuser1": {"player1": {"name": None}}}
    response = client.get("/v1/players/testuser1")
    assert response.status_code == 500


def test_register_player(client):
    response = client.put(
        "/v1/players/testuser1/test-player", json={"name": "Test Player"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Player"
    assert data["stationsUrl"] == "https://registry.radiopad.dev/v1/stations/briceburg"


def test_register_player_for_new_account(client):
    response = client.put(
        "/v1/players/new-account/test-player", json={"name": "Test Player"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Player"

    response = client.get("/v1/players/new-account/test-player")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Player"

    response = client.get("/v1/accounts")
    assert response.status_code == 200
    data = response.json()
    assert "new-account" in [item["id"] for item in data["items"]]


def test_update_player(client):
    response = client.put(
        "/v1/players/testuser1/player1", json={"name": "Updated Player"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Player"

    response = client.get("/v1/players/testuser1/player1")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Player"


def test_get_player_not_found(client):
    response = client.get("/v1/players/testuser1/does-not-exist")
    assert response.status_code == 404
