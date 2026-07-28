from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx2 import Response
from starlette.testclient import TestClient

from api.auth import AuthServices
from auth import AccessTokens, RegistryIDToken
from authz import AccountOwners, AuthzStore, SessionRevocations
from datastore import LocalBackend
from tests.api._app import build_client, build_store

_SESSION_SECRET = "test-session-secret-value-32-bytes"
_ACCESS_TOKENS = AccessTokens(_SESSION_SECRET, clock=lambda: 1_700_000_100)


def _token(
    *,
    subject: str,
    email: str | None = None,
    email_verified: bool | None = False,
) -> RegistryIDToken:
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
        AuthServices(
            authenticate_oidc=StubAuthenticator(identities or {}),
            authz_store=authz_store,
            access_tokens=_ACCESS_TOKENS,
        ),
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _access_bearer(token: RegistryIDToken) -> dict[str, str]:
    identity = _ACCESS_TOKENS.identity_from_oidc(token)
    return _bearer(_ACCESS_TOKENS.issue(identity).token)


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
        else _build_client(
            tmp_path,
            AuthServices(authenticate_oidc=None, authz_store=None, access_tokens=None),
        )
    )

    with client:
        response = client.get("auth/status")

    assert response.status_code == 200
    assert response.json() == {"enabled": enabled}
    assert response.headers["cache-control"] == "no-store"


def test_control_access_is_open_when_auth_is_disabled(tmp_path: Path) -> None:
    client = _build_client(
        tmp_path,
        AuthServices(authenticate_oidc=None, authz_store=None, access_tokens=None),
    )

    with client:
        response = client.get("auth/players/testuser1/player1/control")

    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    assert "radiopad-token-expires-at" not in response.headers


def test_control_access_requires_bearer_token_when_auth_is_enabled(tmp_path: Path) -> None:
    client = _auth_client(tmp_path)

    with client:
        response = client.get("auth/players/testuser1/player1/control")

    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer token required"


@pytest.mark.parametrize(
    ("subject", "email"),
    [("owner", "owner@example.com"), ("coowner", "coowner@example.com")],
)
def test_account_owners_have_control_access(tmp_path: Path, subject: str, email: str) -> None:
    id_token = _token(subject=subject, email=email, email_verified=True)
    client = _auth_client(
        tmp_path,
        configure_authz=_with_account_owners("testuser1", "owner@example.com", "coowner@example.com"),
    )

    with client:
        response = client.get(
            "auth/players/testuser1/player1/control",
            headers=_access_bearer(id_token),
        )

    assert response.status_code == 204
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["radiopad-token-expires-at"] == "1700003700"


def test_oidc_id_token_creates_refreshes_and_deletes_rolling_session(tmp_path: Path) -> None:
    client = _auth_client(
        tmp_path,
        {"owner": _token(subject="owner", email="owner@example.com", email_verified=True)},
        _with_account_owners("testuser1", "owner@example.com"),
    )

    with client:
        created = client.post("auth/session", headers=_bearer("owner"))

        assert created.status_code == 200
        assert created.json()["token_type"] == "bearer"
        assert created.json()["identity"] == {
            "subject": "owner",
            "email": "owner@example.com",
            "name": None,
        }
        cookie = created.headers["set-cookie"]
        cookie_lower = cookie.lower()
        assert "radiopad-session=" in cookie_lower
        assert "httponly" in cookie_lower
        assert "Max-Age=2592000" in cookie
        assert "path=/api/auth/session" in cookie_lower
        assert "samesite=none" in cookie_lower
        assert "secure" in cookie_lower
        assert created.headers["cache-control"] == "no-store"

        access_token = created.json()["access_token"]
        control = client.get(
            "auth/players/testuser1/player1/control",
            headers=_bearer(access_token),
        )
        assert control.status_code == 204
        assert control.headers["radiopad-token-expires-at"] == str(created.json()["expires_at"])

        assert client.post("auth/session/refresh").status_code == 403
        refreshed = client.post("auth/session/refresh", headers={"RadioPad-Session": "refresh"})
        assert refreshed.status_code == 200
        assert refreshed.json()["identity"] == created.json()["identity"]
        assert "radiopad-session=" in refreshed.headers["set-cookie"].lower()

        signed_out = client.delete("auth/session")
        assert signed_out.status_code == 204
        assert "expires=Thu, 01 Jan 1970 00:00:00 GMT" in signed_out.headers["set-cookie"]
        assert client.post("auth/session/refresh", headers={"RadioPad-Session": "refresh"}).status_code == 401


def test_revocation_rejects_access_and_refresh_until_oidc_reauthentication(tmp_path: Path) -> None:
    token = _token(subject="owner", email="owner@example.com", email_verified=True)
    authz_store = AuthzStore(
        backend=LocalBackend(base_path=str(tmp_path / "authz"), prefix="authz"),
    )
    authz_store.save_account_owners(AccountOwners(id="testuser1", emails=["owner@example.com"]))
    services = AuthServices(
        authenticate_oidc=StubAuthenticator({"owner": token}),
        authz_store=authz_store,
        access_tokens=_ACCESS_TOKENS,
    )
    client = _build_client(tmp_path, services)

    with client:
        created = client.post("auth/session", headers=_bearer("owner"))
        assert created.status_code == 200
        access_token = created.json()["access_token"]

        authz_store.save_session_revocations(
            SessionRevocations(
                revoked_before=datetime.fromtimestamp(token.iat, tz=UTC),
            )
        )

        assert client.post("auth/session/refresh", headers={"RadioPad-Session": "refresh"}).status_code == 401
        denied = client.get(
            "auth/players/testuser1/player1/control",
            headers=_bearer(access_token),
        )
        assert denied.status_code == 401
        assert denied.json()["detail"] == "Session revoked—sign in again"
        assert client.post("auth/session", headers=_bearer("owner")).status_code == 401


@pytest.mark.parametrize(
    ("headers", "detail"),
    [
        (None, "Bearer token required"),
        ({"Authorization": "Basic invalid"}, "Bearer token required"),
        ({"Authorization": "Bearer    "}, "Bearer token required"),
        (_bearer("oidc-token"), "Invalid access token"),
    ],
    ids=["missing", "wrong-scheme", "empty-bearer", "oidc-token"],
)
def test_account_write_requires_registry_access_token(
    tmp_path: Path,
    headers: dict[str, str] | None,
    detail: str,
) -> None:
    client = _auth_client(tmp_path)

    with client:
        response = _put_station(client, "testuser1", headers)

    assert response.status_code == 401
    assert response.json()["detail"] == detail


@pytest.mark.parametrize(
    ("subject", "email"),
    [("owner", "owner@example.com"), ("coowner", "coowner@example.com")],
)
def test_account_owners_can_write_owned_resource(tmp_path: Path, subject: str, email: str) -> None:
    id_token = _token(subject=subject, email=email, email_verified=True)
    client = _auth_client(
        tmp_path,
        configure_authz=_with_account_owners("testuser1", "owner@example.com", "coowner@example.com"),
    )

    with client:
        response = _put_station(client, "testuser1", _access_bearer(id_token))

    assert response.status_code == 200
    assert response.json()["call_sign"] == "KEXP"


def test_account_owner_cannot_write_other_account(tmp_path: Path) -> None:
    id_token = _token(subject="owner", email="owner@example.com", email_verified=True)
    client = _auth_client(
        tmp_path,
        configure_authz=_with_account_owners("testuser1", "owner@example.com"),
    )

    with client:
        response = _put_station(client, "testuser2", _access_bearer(id_token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Account owner access required"


@pytest.mark.parametrize("email_verified", [False, None])
def test_account_owner_email_must_be_explicitly_verified(
    tmp_path: Path,
    email_verified: bool | None,
) -> None:
    id_token = _token(
        subject="owner",
        email="owner@example.com",
        email_verified=email_verified,
    )
    client = _auth_client(
        tmp_path,
        configure_authz=_with_account_owners("testuser1", "owner@example.com"),
    )

    with client:
        response = _put_station(client, "testuser1", _access_bearer(id_token))

    assert response.status_code == 403
    assert response.json()["detail"] == "Account owner access required"
