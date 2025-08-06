import pytest

from models.station_preset import StationPreset


def test_list_station_presets(client):
    """Test listing global station presets."""
    response = client.get("/v1/station-presets")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1  # Only the global 'briceburg' preset
    assert data["items"][0]["id"] == "briceburg"
    assert data["items"][0]["account_id"] is None


def test_get_station_preset(client):
    """Test getting a single station preset by ID."""
    response = client.get("/v1/station-presets/briceburg")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "briceburg"
    assert data["name"] == "Briceburg"
    assert len(data["stations"]) > 0


def test_get_station_preset_not_found(client):
    """Test getting a non-existent station preset."""
    response = client.get("/v1/station-presets/does-not-exist")
    assert response.status_code == 404


def test_register_new_station_preset(client):
    """Test creating a new station preset for a user."""
    preset_id = "my-custom-preset"
    preset_data = {
        "name": "My Custom Preset",
        "stations": [
            {"title": "A Cool Station", "url": "https://cool.station/stream"},
            {
                "title": "A Colorful Station",
                "url": "https://colorful.station/stream",
                "color": "#FF0000",
            },
        ],
    }
    response = client.put(
        f"/v1/station-presets/{preset_id}?account_id=testuser1", json=preset_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == preset_id
    assert data["name"] == "My Custom Preset"
    assert data["account_id"] == "testuser1"
    # In the test client, the key may be present with a None value.
    # In a real server, the key would be omitted. This test handles both.
    assert data["stations"][0].get("color") is None
    assert data["stations"][1]["color"] == "#FF0000"  # Custom color

    # Verify it's retrievable via GET
    response = client.get(f"/v1/station-presets/{preset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "My Custom Preset"
    assert data["stations"][1]["color"] == "#FF0000"


def test_update_station_preset(client):
    """Test updating an existing station preset."""
    preset_id = "briceburg"
    updated_data = {
        "name": "Briceburg Updated",
        "stations": [
            {"title": "WWOZ", "url": "https://www.wwoz.org/listen/hi"},
            {"title": "New Station", "url": "https://new.station/stream"},
        ],
    }
    response = client.put(f"/v1/station-presets/{preset_id}", json=updated_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Briceburg Updated"
    assert len(data["stations"]) == 2

    # Verify the update is persisted
    response = client.get(f"/v1/station-presets/{preset_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["stations"]) == 2


def test_list_station_presets_for_account(client):
    """Test that listing presets for an account includes global and custom presets."""
    # First, create a custom preset for testuser1
    client.put(
        "/v1/station-presets/my-preset?account_id=testuser1",
        json={
            "name": "My Preset",
            "stations": [{"title": "A", "url": "https://a.com"}],
        },
    )

    # List presets for testuser1
    response = client.get("/v1/station-presets?account_id=testuser1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # briceburg (global) + my-preset (custom)
    ids = {item["id"] for item in data["items"]}
    assert "briceburg" in ids
    assert "my-preset" in ids

    # List presets for testuser2 (should only see global)
    response = client.get("/v1/station-presets?account_id=testuser2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "briceburg"


def test_register_preset_with_empty_stations(client):
    """Test that a user can create a preset with an empty list of stations."""
    preset_id = "empty-preset"
    preset_data = {"name": "Empty Preset", "stations": []}
    response = client.put(
        f"/v1/station-presets/{preset_id}?account_id=testuser1", json=preset_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == preset_id
    assert data["name"] == "Empty Preset"
    assert data["stations"] == []

    # Verify it's retrievable via GET
    response = client.get(f"/v1/station-presets/{preset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["stations"] == []
