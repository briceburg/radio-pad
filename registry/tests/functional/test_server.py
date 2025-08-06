import pytest


@pytest.mark.functional
def test_real_server_omits_none_values(functional_client):
    """
    A functional test to verify the real Uvicorn server omits None values
    from the JSON response, which confirms `response_model_exclude_none=True`
    is working as expected.
    """
    preset_id = "functional-test-preset"
    preset_data = {
        "name": "Functional Test Preset",
        "stations": [
            {"name": "No Color Station", "url": "https://no-color.com"},
            {
                "name": "Color Station",
                "url": "https://color.com",
                "color": "#123456",
            },
        ],
    }

    # Use httpx to make a real HTTP request to the running server
    response = functional_client.put(
        f"/v1/accounts/testuser1/presets/{preset_id}",
        json=preset_data,
    )

    assert response.status_code == 200
    data = response.json()

    # The crucial assertion: the 'color' key should be missing for the first station
    assert "color" not in data["stations"][0]
    assert data["stations"][1]["color"] == "#123456"
