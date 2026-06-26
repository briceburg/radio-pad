import httpx
import pytest


@pytest.mark.functional
def test_real_server_omits_none_values(functional_client: httpx.Client) -> None:
    """
    A functional test to verify the real Uvicorn server omits None values
    from the JSON response, which confirms `response_model_exclude_none=True`
    is working as expected.
    """
    preset_id = "functional-test-preset"
    preset_data = {
        "name": "Functional Test Preset",
        "description": "Visible description",
        "stations": [{"name": "Test Station", "url": "https://station.example/stream"}],
    }

    # Use httpx to make a real HTTP request to the running server
    response = functional_client.put(
        f"accounts/testuser1/presets/{preset_id}",
        json=preset_data,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["description"] == "Visible description"
    assert "category" not in data
