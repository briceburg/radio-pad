import httpx
import pytest


@pytest.mark.functional
def test_real_server_omits_none_values(functional_client: httpx.Client) -> None:
    """
    A functional test to verify the real Uvicorn server omits None values
    from the JSON response, which confirms `response_model_exclude_none=True`
    is working as expected.
    """
    radio_dial_data = {
        "name": "Functional Test RadioDial",
        "description": "Visible description",
        "stations": ["community/WWOZ"],
    }

    # Use httpx to make a real HTTP request to the running server
    response = functional_client.put(
        "accounts/testuser1/radio-dials/functional-test",
        json=radio_dial_data,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["description"] == "Visible description"
    assert "display_name" not in data["stations"][0]
