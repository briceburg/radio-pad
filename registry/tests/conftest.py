import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

# Add the src directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from registry import create_app


@pytest.fixture
def client():
    # hint to app that we're in unit test mode,
    # enables connexion response validation.
    app = create_app(in_unit_test=True)
    return TestClient(app)
