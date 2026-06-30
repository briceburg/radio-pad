from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from httpx2 import Response
from starlette.testclient import TestClient

from api.auth import AuthServices
from auth import AccountOwners, AuthzStore, RegistryIDToken
from datastore import LocalBackend
from tests.api._app import build_client, build_store


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


def _build_client(tmp_path: Path, auth_services: AuthServices) -> TestClient:
    return build_client(build_store(tmp_path / "data", seed=True), auth_services)


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


def _with_account_owners(account_id: str, *emails: str) -> Callable[[AuthzStore], None]:
    def configure_authz(store: AuthzStore) -> None:
        store.save_account_owners(AccountOwners(id=account_id, emails=list(emails)))

    return configure_authz


def _put_station(client: TestClient, account_id: str, headers: dict[str, str] | None = None) -> Response:
    return client.put(
        f"accounts/{account_id}/stations/KEXP",
        headers=headers or {},
        json={"stream_url": "https://example.com/kexp"},
    )


def test_public_reads_remain_open_when_auth_enabled(tmp_path: Path) -> None:
    client = _auth_client(tmp_path)

    with client:
        assert client.get("accounts/testuser1").status_code == 200
        assert client.get("accounts/community/stations/WWOZ").status_code == 200
        assert client.get("accounts/community/radio-dials/briceburg").status_code == 200
        assert client.get("accounts/testuser1/players/player1").status_code == 200


@pytest.mark.parametrize("enabled", [False, True])
def test_auth_status_reports_current_mode(tmp_path: Path, enabled: bool) -> None:
    client = (
        _auth_client(tmp_path)
        if enabled
        else _build_client(tmp_path, AuthServices(authenticate_user=None, authz_store=None))
    )

    with client:
        response = client.get("auth/status")

    assert response.status_code == 200
    assert response.json() == {"enabled": enabled}
    assert response.headers["cache-control"] == "no-store"


def test_control_access_is_open_when_auth_is_disabled(tmp_path: Path) -> None:
    client = _build_client(tmp_path, AuthServices(authenticate_user=None, authz_store=None))

    with client:
        response = client.get("auth/players/testuser1/player1/control")

    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"


def test_control_access_requires_bearer_token_when_auth_is_enabled(tmp_path: Path) -> None:
    client = _auth_client(tmp_path)

    with client:
        response = client.get("auth/players/testuser1/player1/control")

    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer token required"


@pytest.mark.parametrize(
    ("token", "email"),
    [("owner", "owner@example.com"), ("coowner", "coowner@example.com")],
)
def test_account_owners_have_control_access(tmp_path: Path, token: str, email: str) -> None:
    client = _auth_client(
        tmp_path,
        {token: _token(subject=token, email=email, email_verified=True)},
        _with_account_owners("testuser1", "owner@example.com", "coowner@example.com"),
    )

    with client:
        response = client.get(
            "auth/players/testuser1/player1/control",
            headers=_bearer(token),
        )

    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"


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


@pytest.mark.parametrize(
    ("token", "email"),
    [("owner", "owner@example.com"), ("coowner", "coowner@example.com")],
)
def test_account_owners_can_write_owned_resource(tmp_path: Path, token: str, email: str) -> None:
    client = _auth_client(
        tmp_path,
        {token: _token(subject=token, email=email, email_verified=True)},
        _with_account_owners("testuser1", "owner@example.com", "coowner@example.com"),
    )

    with client:
        response = _put_station(client, "testuser1", _bearer(token))

    assert response.status_code == 200
    assert response.json()["call_sign"] == "KEXP"


def test_account_owner_cannot_write_other_account(tmp_path: Path) -> None:
    client = _auth_client(
        tmp_path,
        {"owner": _token(subject="owner", email="owner@example.com", email_verified=True)},
        _with_account_owners("testuser1", "owner@example.com"),
    )

    with client:
        response = _put_station(client, "testuser2", _bearer("owner"))

    assert response.status_code == 403
    assert response.json()["detail"] == "Account owner access required"
