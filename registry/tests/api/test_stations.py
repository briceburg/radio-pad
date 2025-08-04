def test_get_station_presets(client):
    response = client.get("/v1/station-presets")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert isinstance(data["items"], list)


def test_get_station_list_invalid_data_returns_500(client, monkeypatch):
    """Test that getting a station list with invalid data returns a 500 error."""
    from data.store import store

    monkeypatch.setattr(
        store,
        "_store",
        type(
            "MockStore",
            (),
            {"station_presets": {"briceburg": [{"name": "invalid station"}]}},
        ),
    )
    response = client.get("/v1/stations/briceburg")
    assert response.status_code == 500


# TODO: add preset fixtures to further exercise. check for 404s.


def test_get_station_list(client):
    response = client.get("/v1/stations/briceburg")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "stations" in data
    assert isinstance(data["stations"], list)
    # test that the station list is properly formatted
    from models.station import Station

    for station in data["stations"]:
        Station.model_validate(station)
