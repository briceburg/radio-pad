import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from datastore import DataStore, LocalBackend
from lib.constants import BASE_DIR
from models import Account, GlobalStationPreset, Player, Station
from registry import create_app


def _seed_store(ds: DataStore) -> None:
    """Pre-populate a DataStore with consistent test data."""
    ds.accounts.save(Account.model_validate({"id": "testuser1", "name": "Test User 1"}))
    ds.accounts.save(Account.model_validate({"id": "testuser2", "name": "Test User 2"}))
    ds.players.save(Player.model_validate({"id": "player1", "account_id": "testuser1", "name": "Player 1"}))
    ds.players.save(Player.model_validate({"id": "player2", "account_id": "testuser1", "name": "Player 2"}))
    ds.players.save(Player.model_validate({"id": "player3", "account_id": "testuser2", "name": "Player 3"}))
    ds.global_presets.save(
        GlobalStationPreset.model_validate(
            {
                "id": "briceburg",
                "name": "Briceburg",
                "stations": [Station.model_validate({"name": "WWOZ", "url": "https://www.wwoz.org/listen/hi"})],
            }
        )
    )


def _reset_dir(path: Path) -> Path:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _build_store(data_dir: Path, *, seed: bool = False) -> DataStore:
    store = DataStore(backend=LocalBackend(base_path=str(data_dir)))
    if seed:
        _seed_store(store)
    return store


def _build_client(store: DataStore) -> TestClient:
    app = create_app()

    from api.types import get_store
    from lib.constants import API_PREFIX

    app.dependency_overrides[get_store] = lambda: store
    app.state.store = store
    return TestClient(app, raise_server_exceptions=False, base_url=f"http://testserver{API_PREFIX}/")


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
    test_store = _build_store(data_dir)
    yield test_store
    shutil.rmtree(data_dir)


@pytest.fixture(autouse=True)
def seeded_store(mock_store: DataStore) -> DataStore:
    """Cleans and re-seeds the mock_store for each test."""
    assert isinstance(mock_store.backend, LocalBackend)
    _reset_dir(mock_store.backend.base_path)
    _seed_store(mock_store)
    return mock_store


@pytest.fixture(scope="session")
def client(mock_store: DataStore) -> Generator[TestClient]:
    with _build_client(mock_store) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def ro_mock_store(unit_tests_root: Path) -> Generator[DataStore]:
    """Session-scoped DataStore for read-only tests (seeded once)."""
    data_dir = _reset_dir(unit_tests_root / "api" / "ro_data")
    store = _build_store(data_dir, seed=True)
    yield store


@pytest.fixture(scope="session")
def ro_client(ro_mock_store: DataStore) -> Generator[TestClient]:
    """Session-scoped TestClient bound to the read-only store."""
    with _build_client(ro_mock_store) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def session_monkeypatch() -> Generator[pytest.MonkeyPatch]:
    """Session-scoped monkeypatch fixture to avoid pytest-mock dependency."""
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()
