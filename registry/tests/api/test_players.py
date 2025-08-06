def test_get_players(client):
    response = client.get("/v1/accounts/testuser1/players")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert data["total"] == 2
    assert isinstance(data["items"], list)


def test_list_players_invalid_data_returns_500(client, mock_store):
    """
    Test that the API returns a 500 error if the data in the store is invalid.
    """
    # Inject invalid data directly into the mock store's internal structure
    mock_store.accounts._accounts["testuser1"]["players"]["player1"] = {"name": None}
    response = client.get("/v1/accounts/testuser1/players")
    assert response.status_code == 500


def test_register_player(client):
    response = client.put(
        "/v1/accounts/testuser1/players/test-player", json={"name": "Test Player"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Player"
    assert data["stationsUrl"] == "https://registry.radiopad.dev/v1/presets/briceburg"


def test_register_player_for_new_account(client):
    response = client.put(
        "/v1/accounts/new-account/players/test-player", json={"name": "Test Player"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Player"

    response = client.get("/v1/accounts/new-account/players/test-player")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Player"

    response = client.get("/v1/accounts")
    assert response.status_code == 200
    data = response.json()
    assert "new-account" in [item["id"] for item in data["items"]]


def test_update_player(client):
    response = client.put(
        "/v1/accounts/testuser1/players/player1", json={"name": "Updated Player"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Player"

    response = client.get("/v1/accounts/testuser1/players/player1")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Player"


def test_get_player_not_found(client):
    response = client.get("/v1/accounts/testuser1/players/does-not-exist")
    assert response.status_code == 404


def test_update_player_preserves_existing_data(client, mock_store):
    """
    Test that updating a player with a partial payload preserves existing data,
    and that the change is persisted correctly for subsequent GET requests.
    """
    # Arrange: Add more data to an existing player in the mock store
    original_stations_url = "https://original.url/stations.json"
    mock_store.accounts._accounts["testuser1"]["players"]["player1"][
        "stationsUrl"
    ] = original_stations_url

    # Act: Update only the name of the player
    response = client.put(
        "/v1/accounts/testuser1/players/player1", json={"name": "Updated Player Name"}
    )

    # Assert (PUT response)
    assert response.status_code == 200
    put_data = response.json()
    assert put_data["name"] == "Updated Player Name"
    assert put_data["stationsUrl"] == original_stations_url

    # Assert (subsequent GET request)
    response = client.get("/v1/accounts/testuser1/players/player1")
    assert response.status_code == 200
    get_data = response.json()
    assert get_data["name"] == "Updated Player Name"
    assert get_data["stationsUrl"] == original_stations_url
