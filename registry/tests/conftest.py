import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from registry import create_app


@pytest.fixture
def client():
    app = create_app()
    # Using a `with` statement for the TestClient ensures that the app's
    # lifespan events (startup and shutdown) are correctly triggered.
    # This is crucial for initializing resources like our data store.
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client
