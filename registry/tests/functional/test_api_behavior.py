import pytest
from starlette.testclient import TestClient


@pytest.mark.functional
def test_response_omits_none_values(functional_client: TestClient) -> None:
    """Verify that response models configured to exclude None omit those values."""
    radio_dial_data = {
        "name": "Functional Test RadioDial",
        "stations": ["community/WWOZ"],
    }

    response = functional_client.put(
        "accounts/testuser1/radio-dials/functional-test",
        json=radio_dial_data,
    )

    assert response.status_code == 200
    data = response.json()

    assert "description" not in data
