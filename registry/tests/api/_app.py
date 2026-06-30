from pathlib import Path

from starlette.testclient import TestClient

from api.auth import AuthServices
from datastore import DataStore, LocalBackend
from models import AccountSpec, PlayerSpec, RadioDialSpec, StationSpec
from registry import create_app


def seed_store(ds: DataStore) -> None:
    ds.accounts.upsert("testuser1", AccountSpec(name="Test User 1"))
    ds.accounts.upsert("testuser2", AccountSpec(name="Test User 2"))
    ds.accounts.upsert("community", AccountSpec(name="RadioPad Community"))
    ds.stations.upsert(
        "community",
        "WWOZ",
        StationSpec.model_validate({"stream_url": "https://www.wwoz.org/listen/hi"}),
    )
    ds.stations.upsert(
        "community",
        "KEXP",
        StationSpec.model_validate({"stream_url": "https://kexp.example/stream"}),
    )
    ds.radio_dials.upsert(
        "briceburg",
        RadioDialSpec(
            name="Casa Briceburg",
            discoverable=True,
            stations=["community/WWOZ", "community/KEXP"],
        ),
        path_params={"account_id": "community"},
    )
    for player_id, account_id in [
        ("player1", "testuser1"),
        ("player2", "testuser1"),
        ("player3", "testuser2"),
    ]:
        ds.players.upsert(
            player_id,
            PlayerSpec(
                name=player_id.replace("player", "Player "),
                radio_dial="community/briceburg" if account_id == "testuser1" else None,
            ),
            path_params={"account_id": account_id},
        )


def build_store(data_dir: Path, *, seed: bool = False) -> DataStore:
    store = DataStore(backend=LocalBackend(base_path=str(data_dir)))
    if seed:
        seed_store(store)
    return store


def build_client(store: DataStore, auth_services: AuthServices | None = None) -> TestClient:
    from api.types import get_store
    from lib.constants import API_PREFIX

    app = create_app(profiles=["api"])
    app.dependency_overrides[get_store] = lambda: store
    app.state.store = store
    app.state.auth = auth_services or AuthServices(authenticate_user=None, authz_store=None)
    return TestClient(
        app,
        raise_server_exceptions=False,
        base_url=f"http://testserver{API_PREFIX}/",
    )
