def test_get_players(client):
    response = client.get("/v1/players/briceburg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_get_players_invalid_data_returns_500(client, monkeypatch):
    from data.store import store

    monkeypatch.setattr(
        store,
        "_store",
        type(
            "MockStore", (), {"players": {"briceburg": {"living-room": {"name": None}}}}
        ),
    )
    response = client.get("/v1/players/briceburg")
    assert response.status_code == 500


def test_register_player(client):
    response = client.put(
        "/v1/players/briceburg/test-player", json={"name": "Test Player"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Player"
    assert data["stationsUrl"] == "https://registry.radiopad.dev/v1/stations/briceburg"


def test_register_player_invalid_payload_returns_422(client):
    response = client.put("/v1/players/briceburg/test-player", json={"name": None})
    assert response.status_code == 422


# TODO: add preset fixtures to further exercise. check for 404s.
