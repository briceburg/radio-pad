def test_get_station_presets(client):
    response = client.get("/v1/station-presets")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "items" in data
    assert "page" in data
    assert "per_page" in data
    assert "total" in data
    assert data["total"] == 2
    assert isinstance(data["items"], list)


def test_get_station_list_invalid_data_returns_500(client, mock_store):
    """Test that getting a station list with invalid data returns a 500 error."""
    mock_store._station_presets = {
        "preset1": {"id": "preset1", "stations": [{"name": "invalid station"}]}
    }
    response = client.get("/v1/stations/preset1")
    assert response.status_code == 500


def test_get_station_list_not_found(client):
    response = client.get("/v1/stations/does-not-exist")
    assert response.status_code == 404


def test_get_station_list(client):
    response = client.get("/v1/stations/preset1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    data = response.json()
    assert "stations" in data
    assert isinstance(data["stations"], list)
    # test that the station list is properly formatted
    from models.station import Station

    for station in data["stations"]:
        Station.model_validate(station)
