from collections.abc import Generator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from datastore import DataStore
from tests.api._app import build_client, build_store


@pytest.fixture
def mock_store(tmp_path: Path) -> DataStore:
    """Seed isolated API data only for tests that request the store or client."""
    return build_store(tmp_path / "data", seed=True)


@pytest.fixture
def client(mock_store: DataStore) -> Generator[TestClient]:
    with build_client(mock_store) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def session_monkeypatch() -> Generator[pytest.MonkeyPatch]:
    """Session-scoped monkeypatch fixture to avoid pytest-mock dependency."""
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()
