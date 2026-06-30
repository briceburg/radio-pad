from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from auth import AccountOwners, AuthenticatedIdentity, AuthzStore
from datastore.backends import LocalBackend
from lib.constants import BASE_DIR


def _identity(subject: str, email: str) -> AuthenticatedIdentity:
    return AuthenticatedIdentity(
        issuer="https://issuer.example",
        subject=subject,
        email=email,
        email_verified=True,
    )


def test_authz_store_uses_separate_local_path(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    authz_path = tmp_path / "authz"
    monkeypatch.setenv("REGISTRY_AUTHZ_PATH", str(authz_path))
    monkeypatch.setenv("REGISTRY_AUTHZ_PREFIX", "authz")

    store = AuthzStore()

    assert isinstance(store.backend, LocalBackend)
    assert store.backend.base_path == authz_path
    assert store.backend.prefix == "authz"


def test_authz_store_matches_verified_email_and_subject(tmp_path: Path) -> None:
    backend = LocalBackend(base_path=str(tmp_path / "authz"), prefix="authz")
    store = AuthzStore(backend=backend)
    identity = _identity("user-123", "owner@example.com")

    store.save_account_owners(
        AccountOwners(
            id="testuser1",
            subjects=[identity.subject_key],
            emails=["SECOND-OWNER@example.com"],
        )
    )

    assert store.is_account_owner("testuser1", identity)
    assert store.is_account_owner(
        "testuser1",
        _identity("user-456", "second-owner@example.com"),
    )
    assert not store.is_account_owner(
        "testuser2",
        _identity("user-999", "other@example.com"),
    )


def test_authz_store_seeds_checked_in_account_owners(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("REGISTRY_SEED_DATA_PATH", str(BASE_DIR / "seed-data"))
    store = AuthzStore(backend=LocalBackend(base_path=str(tmp_path / "authz"), prefix="authz"))
    store.seed()

    identity = _identity("briceburg-subject", "briceburg@gmail.com")

    assert store.is_account_owner("briceburg", identity)
    assert store.is_account_owner("community", identity)
