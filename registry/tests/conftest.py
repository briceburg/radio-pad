import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

# Add the src and tests directories to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.store import DataStore
from registry import create_app


# a mock datastore with known values for testing
@pytest.fixture
def mock_store(monkeypatch):
    store = DataStore()
    store._accounts = {
        "testuser1": {"name": "Test User 1"},
        "testuser2": {"name": "Test User 2"},
    }
    store._players = {
        "testuser1": {
            "player1": {"name": "Player 1"},
            "player2": {"name": "Player 2"},
        },
        "testuser2": {
            "player3": {"name": "Player 3"},
        },
    }
    store._station_presets = {
        "preset1": {"id": "preset1", "stations": []},
        "preset2": {"id": "preset2", "stations": []},
    }

    from registry import store as app_store

    monkeypatch.setattr(app_store, "_store", store)
    return store


@pytest.fixture
def client(mock_store):
    app = create_app()
    # Using a `with` statement for the TestClient ensures that the app's
    # lifespan events (startup and shutdown) are correctly triggered.
    # This is crucial for initializing resources like our data store.
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
