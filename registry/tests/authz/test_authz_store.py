from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import boto3
import pytest
from _pytest.monkeypatch import MonkeyPatch
from moto import mock_aws
from pydantic import ValidationError

from auth import AuthenticatedIdentity
from authz import AccountOwners, AuthzStore, SessionRevocations
from datastore import DataStore
from datastore.backends import GitBackend, LocalBackend, S3Backend
from datastore.core import ObjectStore, storage_json
from lib.constants import BASE_DIR
from models import AccountSpec
from tests.datastore._git_helpers import init_repo


def _identity(subject: str, email: str) -> AuthenticatedIdentity:
    return AuthenticatedIdentity(
        issuer="https://issuer.example",
        subject=subject,
        authenticated_at=1_700_000_000,
        email=email,
        email_verified=True,
    )


def test_authz_store_uses_separate_local_path(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    authz_path = tmp_path / "authz"
    monkeypatch.setenv("REGISTRY_AUTHZ_BACKEND_PATH", str(authz_path))

    store = AuthzStore()

    assert isinstance(store.backend, LocalBackend)
    assert store.backend.base_path == authz_path
    assert store.backend.prefix == "authz"


@pytest.fixture
def s3_authz(monkeypatch: MonkeyPatch) -> Generator[tuple[AuthzStore, Any]]:
    with mock_aws():
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
        monkeypatch.setenv("REGISTRY_AUTHZ_BACKEND", "s3")
        monkeypatch.setenv("REGISTRY_AUTHZ_BACKEND_S3_BUCKET", "private-authz")
        client = boto3.client("s3")
        client.create_bucket(Bucket="private-authz")
        yield AuthzStore(), client


def test_authz_store_creates_s3_backend_from_env(s3_authz: tuple[AuthzStore, Any]) -> None:
    store, _client = s3_authz

    assert isinstance(store.backend, S3Backend)
    assert store.backend.bucket == "private-authz"
    assert store.backend.prefix == "authz"
    store.check_backend_access()


def test_authz_store_checks_access_with_point_read() -> None:
    backend = Mock(spec=ObjectStore)
    backend.get.return_value = (None, None)

    AuthzStore(backend=backend).check_backend_access()

    backend.get.assert_called_once_with("__access_check__", "accounts")
    backend.list.assert_not_called()


def test_authz_store_requires_s3_bucket(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("REGISTRY_AUTHZ_BACKEND", "s3")
    monkeypatch.delenv("REGISTRY_AUTHZ_BACKEND_S3_BUCKET", raising=False)

    with pytest.raises(ValueError, match="no bucket is configured"):
        AuthzStore()


def test_authz_store_rejects_unknown_backend(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("REGISTRY_AUTHZ_BACKEND", "unknown")

    with pytest.raises(ValueError, match="Unsupported REGISTRY_AUTHZ_BACKEND"):
        AuthzStore()


def test_authz_store_can_share_local_backend_with_data(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    shared_path = tmp_path / "shared"
    monkeypatch.setenv("REGISTRY_DATA_BACKEND", "local")
    monkeypatch.setenv("REGISTRY_DATA_BACKEND_PATH", str(shared_path))

    data = DataStore()
    authz = AuthzStore()
    assert isinstance(data.backend, LocalBackend)
    assert isinstance(authz.backend, LocalBackend)
    assert data.backend.base_path == authz.backend.base_path
    data.accounts.upsert("briceburg", AccountSpec(name="Briceburg"))
    authz.save_account_owners(AccountOwners(id="briceburg", emails=["owner@example.com"]))

    assert (shared_path / "data" / "accounts" / "briceburg.json").is_file()
    assert (shared_path / "authz" / "accounts" / "briceburg.json").is_file()


def test_authz_store_can_share_git_checkout_with_data(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    shared_path = tmp_path / "shared"
    init_repo(shared_path)
    monkeypatch.setenv("REGISTRY_DATA_BACKEND", "git")
    monkeypatch.setenv("REGISTRY_DATA_BACKEND_PATH", str(shared_path))
    monkeypatch.setenv("REGISTRY_DATA_BACKEND_GIT_REMOTE_URL", "")
    monkeypatch.setenv("REGISTRY_GIT_FETCH_TTL_SECONDS", "17")
    monkeypatch.setenv("REGISTRY_GIT_AUTHOR_NAME", "shared author")
    monkeypatch.setenv("REGISTRY_GIT_AUTHOR_EMAIL", "shared@example.com")
    monkeypatch.setenv("REGISTRY_DATA_BACKEND_GIT_SSH_KEY_PATH", "/tmp/shared-key")

    data = DataStore()
    authz = AuthzStore()
    assert isinstance(data.backend, GitBackend)
    assert isinstance(authz.backend, GitBackend)
    assert data.backend._lock_path == authz.backend._lock_path
    assert authz.backend.fetch_ttl_seconds == 17
    assert authz.backend.author_name == "shared author"
    assert authz.backend.author_email == "shared@example.com"
    assert authz.backend.ssh_key_path == "/tmp/shared-key"
    data.accounts.upsert("briceburg", AccountSpec(name="Briceburg"))
    authz.save_account_owners(AccountOwners(id="briceburg", emails=["owner@example.com"]))

    assert (shared_path / "data" / "accounts" / "briceburg.json").is_file()
    assert (shared_path / "authz" / "accounts" / "briceburg.json").is_file()


def test_authz_store_can_use_separate_git_checkout(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    data_path = tmp_path / "data"
    authz_path = tmp_path / "authz"
    init_repo(authz_path)
    monkeypatch.setenv("REGISTRY_DATA_BACKEND", "local")
    monkeypatch.setenv("REGISTRY_DATA_BACKEND_PATH", str(data_path))
    monkeypatch.setenv("REGISTRY_AUTHZ_BACKEND", "git")
    monkeypatch.setenv("REGISTRY_AUTHZ_BACKEND_PATH", str(authz_path))
    monkeypatch.setenv("REGISTRY_AUTHZ_BACKEND_GIT_REMOTE_URL", "")
    monkeypatch.setenv("REGISTRY_GIT_FETCH_TTL_SECONDS", "17")

    authz = AuthzStore()

    assert isinstance(authz.backend, GitBackend)
    assert authz.backend.repo_path == authz_path
    assert authz.backend.prefix == "authz"
    assert authz.backend.remote_url == ""
    assert authz.backend.fetch_ttl_seconds == 17


def test_authz_store_can_share_s3_bucket_with_data(
    monkeypatch: MonkeyPatch,
    s3_authz: tuple[AuthzStore, Any],
) -> None:
    _configured_authz, client = s3_authz
    monkeypatch.delenv("REGISTRY_AUTHZ_BACKEND")
    monkeypatch.delenv("REGISTRY_AUTHZ_BACKEND_S3_BUCKET")
    monkeypatch.setenv("REGISTRY_DATA_BACKEND", "s3")
    monkeypatch.setenv("REGISTRY_DATA_BACKEND_S3_BUCKET", "private-authz")

    data = DataStore()
    authz = AuthzStore()
    assert isinstance(data.backend, S3Backend)
    assert isinstance(authz.backend, S3Backend)
    assert data.backend.bucket == authz.backend.bucket
    data.accounts.upsert("briceburg", AccountSpec(name="Briceburg"))
    authz.save_account_owners(AccountOwners(id="briceburg", emails=["owner@example.com"]))
    keys = {item["Key"] for item in client.list_objects_v2(Bucket="private-authz").get("Contents", [])}

    assert keys == {
        "authz/accounts/briceburg.json",
        "data/accounts/briceburg.json",
    }


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


def test_account_owners_normalizes_and_requires_principals() -> None:
    owners = AccountOwners(
        id="briceburg",
        emails=[" Owner@Example.com ", "owner@example.com"],
        subjects=[" oidc:https://accounts.google.com:123 ", "oidc:https://accounts.google.com:123"],
    )

    assert owners.emails == ["owner@example.com"]
    assert owners.subjects == ["oidc:https://accounts.google.com:123"]

    with pytest.raises(ValidationError, match="at least one owner"):
        AccountOwners(id="briceburg")


def test_authz_store_observes_external_s3_change(s3_authz: tuple[AuthzStore, Any]) -> None:
    store, raw_client = s3_authz
    assert isinstance(store.backend, S3Backend)
    client = raw_client
    store.save_account_owners(AccountOwners(id="briceburg", emails=["first@example.com"]))
    replacement = {"emails": ["second@example.com"], "subjects": []}
    client.put_object(
        Bucket="private-authz",
        Key="authz/accounts/briceburg.json",
        Body=storage_json(replacement).encode(),
    )

    assert not store.is_account_owner("briceburg", _identity("first", "first@example.com"))
    assert store.is_account_owner("briceburg", _identity("second", "second@example.com"))


def test_session_revocations_support_global_and_user_cutoffs() -> None:
    identity = _identity("user-123", "owner@example.com")
    before_authentication = datetime.fromtimestamp(identity.authenticated_at - 1, tz=UTC)
    at_authentication = datetime.fromtimestamp(identity.authenticated_at, tz=UTC)

    assert SessionRevocations(revoked_before=before_authentication).allows(identity)
    assert not SessionRevocations(revoked_before=at_authentication).allows(identity)
    assert not SessionRevocations(subjects={identity.subject_key: at_authentication}).allows(identity)
    assert not SessionRevocations(emails={"OWNER@EXAMPLE.COM": at_authentication}).allows(identity)
    assert SessionRevocations(subjects={"oidc:https://issuer.example:other": at_authentication}).allows(identity)


def test_session_revocations_are_cached_and_saved_values_invalidate_cache(tmp_path: Path) -> None:
    now = [10.0]
    backend = LocalBackend(base_path=str(tmp_path / "authz"), prefix="authz")
    store = AuthzStore(backend=backend, cache_ttl_seconds=5, cache_clock=lambda: now[0])
    identity = _identity("user-123", "owner@example.com")
    cutoff = datetime.fromtimestamp(identity.authenticated_at, tz=UTC)

    assert store.is_session_allowed(identity)
    backend.save(
        "session-revocations",
        SessionRevocations(revoked_before=cutoff).model_dump(mode="json", exclude={"id"}),
        "policies",
    )
    assert store.is_session_allowed(identity)

    now[0] = 15.0
    assert not store.is_session_allowed(identity)

    store.save_session_revocations(SessionRevocations())
    assert store.is_session_allowed(identity)


def test_checked_in_account_owners_are_seeded(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("REGISTRY_SEED_DATA_PATH", str(BASE_DIR / "seed-data"))
    store = AuthzStore(backend=LocalBackend(base_path=str(tmp_path / "authz"), prefix="authz"))
    store.seed()

    assert store.get_account_owners("briceburg") == AccountOwners(
        id="briceburg",
        emails=["briceburg@gmail.com"],
    )
    assert store.get_account_owners("community") == AccountOwners(
        id="community",
        emails=["briceburg@gmail.com"],
    )
    assert store.get_session_revocations() == SessionRevocations()
