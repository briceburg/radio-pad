import multiprocessing
import time

import httpx
import pytest
import uvicorn


def run_server():
    """A simple function to run the Uvicorn server."""
    uvicorn.run("src.registry:app", host="127.0.0.1", port=8000, log_level="warning")


@pytest.mark.functional
def test_real_server_omits_none_values():
    """
    A functional test to verify the real Uvicorn server omits None values
    from the JSON response, which confirms `response_model_exclude_none=True`
    is working as expected.
    """
    server_process = multiprocessing.Process(target=run_server)
    try:
        server_process.start()
        # Wait for the server to be ready by polling the health check endpoint
        max_wait = 5  # seconds
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                with httpx.Client() as client:
                    response = client.get("http://127.0.0.1:8000/healthz")
                    if response.status_code == 200:
                        break
            except httpx.ConnectError:
                time.sleep(0.1)  # Wait a bit before retrying
        else:
            pytest.fail("Server did not start within the specified timeout.")

        preset_id = "functional-test-preset"
        preset_data = {
            "name": "Functional Test Preset",
            "stations": [
                {"title": "No Color Station", "url": "https://no-color.com"},
                {
                    "title": "Color Station",
                    "url": "https://color.com",
                    "color": "#123456",
                },
            ],
        }

        # Use httpx to make a real HTTP request to the running server
        preset_data["account_id"] = "testuser1"
        response = httpx.put(
            f"http://127.0.0.1:8000/v1/accounts/testuser1/presets/{preset_id}",
            json=preset_data,
        )

        assert response.status_code == 200
        data = response.json()

        # The crucial assertion: the 'color' key should be missing for the first station
        assert "color" not in data["stations"][0]
        assert data["stations"][1]["color"] == "#123456"

    finally:
        # Ensure the server is always terminated, even if assertions fail
        if server_process.is_alive():
            server_process.terminate()
            server_process.join()
