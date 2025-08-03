def test_get_station_presets(client):
    response = client.get("/v1/station-presets")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert "total_pages" in data
    assert isinstance(data["items"], list)


def test_get_station_presets_invalid_data_returns_500(client, monkeypatch):
    monkeypatch.setattr(
        "api.station_presets.STATION_PRESETS_LIST",
        [{"id": "briceburg"}],  # Invalid: missing lastUpdated
    )
    response = client.get("/v1/station-presets")
    assert response.status_code == 500


# TODO: add preset fixtures to further exercise. check for 404s.
