from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from httpx import Response
from starlette.testclient import TestClient

from api.auth import AuthServices
from auth import AccountAccess, AuthzStore, GlobalAdmins, RegistryIDToken
from datastore import DataStore, LocalBackend
from models import AccountSpec, PlayerSpec, RadioDialSpec, StationSpec
from registry import create_app


def _token(*, subject: str, email: str | None = None, email_verified: bool = False) -> RegistryIDToken:
    return RegistryIDToken(
        iss="https://issuer.example",
        sub=subject,
        aud="radio-pad-remote-control",
        exp=4_102_444_800,
        iat=1_700_000_000,
        email=email,
        email_verified=email_verified,
    )


class StubAuthenticator:
    def __init__(self, identities: dict[str, RegistryIDToken]) -> None:
        self._identities = identities

    def __call__(self, auth_header: str) -> RegistryIDToken:
        token = auth_header.split(" ")[-1]
        if token not in self._identities:
            raise ValueError("Invalid bearer token")
        return self._identities[token]


def _seed_store(ds: DataStore) -> None:
    ds.accounts.upsert("testuser1", AccountSpec(name="Test User 1"))
    ds.accounts.upsert("testuser2", AccountSpec(name="Test User 2"))
    ds.stations.upsert(
        "testuser1",
        "WWOZ",
        StationSpec.model_validate({"stream_url": "https://example.com/wwoz"}),
    )
    ds.radio_dials.upsert(
        "primary",
        RadioDialSpec(name="Primary", stations=["testuser1/WWOZ"]),
        path_params={"account_id": "testuser1"},
    )
    ds.players.upsert(
        "player1",
        PlayerSpec(name="Player 1", radio_dial="testuser1/primary"),
        path_params={"account_id": "testuser1"},
    )


def _build_client(tmp_path: Path, auth_services: AuthServices) -> TestClient:
    from lib import constants

    constants.PROFILES = ["api"]
    data_store = DataStore(backend=LocalBackend(base_path=str(tmp_path / "data"), prefix="registry-v1"))
    _seed_store(data_store)
    app = create_app()

    from api.types import get_store
    from lib.constants import API_PREFIX

    app.dependency_overrides[get_store] = lambda: data_store
    app.state.store = data_store
    app.state.auth = auth_services
    return TestClient(app, raise_server_exceptions=False, base_url=f"http://testserver{API_PREFIX}/")


def _auth_client(
    tmp_path: Path,
    identities: dict[str, RegistryIDToken] | None = None,
    configure_authz: Callable[[AuthzStore], None] | None = None,
) -> TestClient:
    authz_store = AuthzStore(backend=LocalBackend(base_path=str(tmp_path / "authz"), prefix="authz"))
    if configure_authz:
        configure_authz(authz_store)
    return _build_client(
        tmp_path,
        AuthServices(authenticate_user=StubAuthenticator(identities or {}), authz_store=authz_store),
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _with_global_admin(email: str) -> Callable[[AuthzStore], None]:
    def configure_authz(store: AuthzStore) -> None:
        store.save_global_admins(GlobalAdmins(emails=[email]))

    return configure_authz


def _with_account_owner(account_id: str, email: str) -> Callable[[AuthzStore], None]:
    def configure_authz(store: AuthzStore) -> None:
        store.save_account_access(AccountAccess(id=account_id, emails=[email]))

    return configure_authz


def _put_station(client: TestClient, account_id: str, headers: dict[str, str] | None = None) -> Response:
    return cast(
        Response,
        client.put(
            f"accounts/{account_id}/stations/KEXP",
            headers=headers or {},
            json={"stream_url": "https://example.com/kexp"},
        ),
    )


def test_public_reads_remain_open_when_auth_enabled(tmp_path: Path) -> None:
    client = _auth_client(tmp_path)

    with client:
        assert client.get("accounts/testuser1").status_code == 200
        assert client.get("accounts/testuser1/stations/WWOZ").status_code == 200
        assert client.get("accounts/testuser1/radio-dials/primary").status_code == 200
        assert client.get("accounts/testuser1/players/player1").status_code == 200


@pytest.mark.parametrize(
    "headers",
    [None, {"Authorization": "Basic invalid"}, {"Authorization": "Bearer    "}],
    ids=["missing", "wrong-scheme", "empty-bearer"],
)
def test_account_write_requires_bearer_token(tmp_path: Path, headers: dict[str, str] | None) -> None:
    client = _auth_client(tmp_path)

    with client:
        response = _put_station(client, "testuser1", headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer token required"


def test_account_owner_can_write_owned_resource(tmp_path: Path) -> None:
    client = _auth_client(
        tmp_path,
        {"owner": _token(subject="owner", email="owner@example.com", email_verified=True)},
        _with_account_owner("testuser1", "owner@example.com"),
    )

    with client:
        response = _put_station(client, "testuser1", _bearer("owner"))

    assert response.status_code == 200
    assert response.json()["call_sign"] == "KEXP"


def test_account_owner_cannot_write_other_account(tmp_path: Path) -> None:
    client = _auth_client(
        tmp_path,
        {"owner": _token(subject="owner", email="owner@example.com", email_verified=True)},
        _with_account_owner("testuser1", "owner@example.com"),
    )

    with client:
        response = _put_station(client, "testuser2", _bearer("owner"))

    assert response.status_code == 403
    assert response.json()["detail"] == "Account owner or admin access required"


def test_global_admin_can_write_any_account(tmp_path: Path) -> None:
    client = _auth_client(
        tmp_path,
        {"admin": _token(subject="admin", email="admin@example.com", email_verified=True)},
        _with_global_admin("admin@example.com"),
    )

    with client:
        response = _put_station(client, "testuser2", _bearer("admin"))

    assert response.status_code == 200
