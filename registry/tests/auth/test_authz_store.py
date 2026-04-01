from pathlib import Path

from _pytest.monkeypatch import MonkeyPatch

from auth import AccountAccess, AuthenticatedIdentity, AuthzStore, GlobalAdmins
from datastore.backends import LocalBackend


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
    identity = AuthenticatedIdentity(
        issuer="https://issuer.example",
        subject="user-123",
        email="owner@example.com",
        email_verified=True,
    )

    store.save_global_admins(GlobalAdmins(emails=["OWNER@example.com"]))
    store.save_account_access(AccountAccess(id="testuser1", subjects=[identity.subject_key]))

    assert store.is_admin(identity)
    assert store.can_manage_account("testuser1", identity)
    assert not store.can_manage_account(
        "testuser2",
        AuthenticatedIdentity(
            issuer="https://issuer.example",
            subject="user-999",
            email="other@example.com",
            email_verified=True,
        ),
    )


def test_authz_store_seeds_human_friendly_documents(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    seed_root = tmp_path / "seed-data"
    auth_seed_root = seed_root / "auth"
    (auth_seed_root / "accounts").mkdir(parents=True)
    (auth_seed_root / "global-admins.json").write_text('{\n  "emails": ["briceburg@gmail.com"]\n}\n', encoding="utf-8")
    (auth_seed_root / "accounts" / "briceburg.json").write_text(
        '{\n  "emails": ["briceburg@gmail.com"]\n}\n',
        encoding="utf-8",
    )

    monkeypatch.setenv("REGISTRY_SEED_DATA_PATH", str(seed_root))
    store = AuthzStore(backend=LocalBackend(base_path=str(tmp_path / "authz"), prefix="authz"))
    store.seed()

    identity = AuthenticatedIdentity(
        issuer="https://issuer.example",
        subject="briceburg-subject",
        email="briceburg@gmail.com",
        email_verified=True,
    )

    assert store.is_admin(identity)
    assert store.can_manage_account("briceburg", identity)
