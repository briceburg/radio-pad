import pytest


def test_register_account_preset(client):
    """Test creating a new station preset for an account with all fields."""
    account_id = "testuser"
    preset_id = "my-custom-preset"
    preset_data = {
        "name": "My Custom Preset",
        "category": "Personal",
        "description": "My personal list of stations.",
        "stations": [
            {"title": "A Cool Station", "url": "https://cool.station/stream"},
        ],
    }
    response = client.put(
        f"/v1/accounts/{account_id}/presets/{preset_id}", json=preset_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == preset_id
    assert data["name"] == "My Custom Preset"
    assert data["category"] == "Personal"
    assert data["description"] == "My personal list of stations."
    assert data["account_id"] == account_id


def test_register_account_preset_missing_optional_fields(client):
    """Test creating an account preset works when optional fields are missing."""
    account_id = "testuser"
    preset_id = "minimal-preset"
    preset_data = {
        "name": "Minimal Preset",
        "stations": [],
    }
    response = client.put(
        f"/v1/accounts/{account_id}/presets/{preset_id}", json=preset_data
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Minimal Preset"
    assert data.get("category") is None
    assert data.get("description") is None


@pytest.mark.parametrize(
    "missing_field",
    ["name", "stations"],
)
def test_register_account_preset_missing_required_field(client, missing_field):
    """Test that creating an account preset fails if required fields are missing."""
    account_id = "testuser"
    preset_id = "invalid-preset"
    preset_data = {
        "name": "Invalid Preset",
        "stations": [],
    }
    del preset_data[missing_field]
    response = client.put(
        f"/v1/accounts/{account_id}/presets/{preset_id}", json=preset_data
    )
    assert response.status_code == 422


def test_get_account_preset(client):
    """Test getting a single station preset for an account."""
    account_id = "testuser"
    preset_id = "my-preset"
    client.put(
        f"/v1/accounts/{account_id}/presets/{preset_id}",
        json={
            "name": "My Preset",
            "stations": [{"title": "A", "url": "https://a.com"}],
        },
    )

    response = client.get(f"/v1/accounts/{account_id}/presets/{preset_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == preset_id
    assert data["account_id"] == account_id


def test_get_account_preset_not_found(client):
    """Test getting a non-existent account station preset."""
    response = client.get("/v1/accounts/testuser/presets/does-not-exist")
    assert response.status_code == 404


def test_list_account_presets(client):
    """Test listing station presets for an account."""
    account_id = "testuser"
    client.put(
        f"/v1/accounts/{account_id}/presets/my-preset",
        json={
            "name": "My Preset",
            "stations": [{"title": "A", "url": "https://a.com"}],
        },
    )

    # Test without including globals
    response = client.get(f"/v1/accounts/{account_id}/presets")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == "my-preset"
    assert data["items"][0]["account_id"] == account_id
    assert "stations" not in data["items"][0]  # Summary view

    # Test including globals
    response = client.get(f"/v1/accounts/{account_id}/presets?include_globals=true")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2  # my-preset + briceburg (global)
    assert any(item["id"] == "my-preset" for item in data["items"])
    assert any(item["id"] == "briceburg" for item in data["items"])
