import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from datastore import DataStore, LocalBackend
from lib.constants import BASE_DIR
from tests.api._app import build_client, build_store, seed_store


def _reset_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="session")
def unit_tests_root() -> Path:
    """Root directory for unit test data under <project>/tmp/tests/unit."""
    root = BASE_DIR / "tmp" / "tests" / "unit"
    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    return Path(root)


@pytest.fixture(scope="session")
def mock_store(unit_tests_root: Path) -> Generator[DataStore]:
    """
    Session-scoped DataStore rooted in tmp/tests/unit/api/data.

    Per-test isolation is provided by the autouse `seeded_store` fixture, which resets and
    re-seeds this shared backend directory before each test while still allowing inspection
    of test data after a run.
    """
    data_dir = _reset_dir(unit_tests_root / "api" / "data")
    test_store = build_store(data_dir)
    yield test_store
    shutil.rmtree(data_dir)


@pytest.fixture(autouse=True)
def seeded_store(mock_store: DataStore) -> DataStore:
    """Cleans and re-seeds the mock_store for each test."""
    assert isinstance(mock_store.backend, LocalBackend)
    _reset_dir(mock_store.backend.base_path)
    seed_store(mock_store)
    return mock_store


@pytest.fixture(scope="session")
def client(mock_store: DataStore) -> Generator[TestClient]:
    with build_client(mock_store) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def ro_mock_store(unit_tests_root: Path) -> Generator[DataStore]:
    """Session-scoped DataStore for read-only tests (seeded once)."""
    data_dir = _reset_dir(unit_tests_root / "api" / "ro_data")
    store = build_store(data_dir, seed=True)
    yield store


@pytest.fixture(scope="session")
def ro_client(ro_mock_store: DataStore) -> Generator[TestClient]:
    """Session-scoped TestClient bound to the read-only store."""
    with build_client(ro_mock_store) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def session_monkeypatch() -> Generator[pytest.MonkeyPatch]:
    """Session-scoped monkeypatch fixture to avoid pytest-mock dependency."""
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()
