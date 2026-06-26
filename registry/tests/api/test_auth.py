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
from models import Account, GlobalStationPreset, Player, Station
from registry import create_app

FRESH_PRESET = {"name": "Fresh", "stations": [{"name": "A", "url": "https://a.example/stream"}]}


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
    ds.accounts.save(Account.model_validate({"id": "testuser1", "name": "Test User 1"}))
    ds.accounts.save(Account.model_validate({"id": "testuser2", "name": "Test User 2"}))
    ds.players.save(Player.model_validate({"id": "player1", "account_id": "testuser1", "name": "Player 1"}))
    ds.global_presets.save(
        GlobalStationPreset.model_validate(
            {
                "id": "briceburg",
                "name": "Briceburg",
                "stations": [Station.model_validate({"name": "WWOZ", "url": "https://www.wwoz.org/listen/hi"})],
            }
        )
    )


def _build_client(tmp_path: Path, auth_services: AuthServices) -> TestClient:
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
        AuthServices(
            authenticate_user=StubAuthenticator(identities or {}),
            authz_store=authz_store,
        ),
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


def _put_fresh_global_preset(client: TestClient, headers: dict[str, str] | None = None) -> Response:
    return cast(Response, client.put("presets/fresh", headers=headers or {}, json=FRESH_PRESET))


def test_public_reads_remain_open_when_auth_enabled(tmp_path: Path) -> None:
    client = _auth_client(tmp_path)

    with client:
        # All read endpoints must remain public even when auth is enabled
        assert client.get("presets/briceburg").status_code == 200
        assert client.get("accounts/testuser1").status_code == 200
        assert client.get("accounts/testuser1/players/player1").status_code == 200
        assert client.get("accounts/testuser1/players").status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        None,
        {"Authorization": "Basic not-a-bearer-token"},
        {"Authorization": "Bearer    "},
    ],
    ids=["missing", "wrong-scheme", "empty-bearer"],
)
def test_global_preset_write_requires_bearer_token(tmp_path: Path, headers: dict[str, str] | None) -> None:
    client = _auth_client(tmp_path)

    with client:
        response = _put_fresh_global_preset(client, headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer token required"


def test_global_preset_write_requires_admin_access(tmp_path: Path) -> None:
    client = _auth_client(tmp_path, {"owner-token": _token(subject="owner-123")})

    with client:
        response = _put_fresh_global_preset(client, _bearer("owner-token"))

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_can_write_global_preset(tmp_path: Path) -> None:
    client = _auth_client(
        tmp_path,
        {"admin-token": _token(subject="admin-123", email="briceburg@gmail.com", email_verified=True)},
        _with_global_admin("briceburg@gmail.com"),
    )

    with client:
        response = _put_fresh_global_preset(client, _bearer("admin-token"))

    assert response.status_code == 200
    assert response.json()["id"] == "fresh"


def test_account_owner_can_update_owned_account(tmp_path: Path) -> None:
    client = _auth_client(
        tmp_path,
        {"owner-token": _token(subject="owner-123", email="owner@example.com", email_verified=True)},
        _with_account_owner("testuser1", "owner@example.com"),
    )

    with client:
        response = client.put(
            "accounts/testuser1",
            headers=_bearer("owner-token"),
            json={"name": "Updated User 1"},
        )

    assert response.status_code == 200
    assert response.json()["name"] == "Updated User 1"


def test_account_owner_cannot_update_other_account(tmp_path: Path) -> None:
    client = _auth_client(
        tmp_path,
        {"owner-token": _token(subject="owner-123", email="owner@example.com", email_verified=True)},
        _with_account_owner("testuser1", "owner@example.com"),
    )

    with client:
        response = client.put(
            "accounts/testuser2",
            headers=_bearer("owner-token"),
            json={"name": "Updated User 2"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Account owner or admin access required"
