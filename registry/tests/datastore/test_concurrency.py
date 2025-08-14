import pytest

from datastore.backends import JSONFileStore
from datastore.core import ConcurrencyError, ModelStore
from models.account import Account


def test_merge_upsert_conflict_raises_concurrency_error(tmp_path, monkeypatch):
    """Simulate a write-write race: merge_upsert should pass stale ETag and raise ConcurrencyError."""
    backend = JSONFileStore(str(tmp_path))
    repo = ModelStore(backend, model=Account, path_template="accounts/{id}")

    # Seed initial value
    repo.save(Account(id="acct", name="One"))

    # Snapshot stale state (data, etag)
    stale_data, stale_version = backend.get("acct", "accounts")
    assert stale_version is not None

    # Concurrent writer updates the document
    backend.save("acct", {"name": "Two"}, "accounts")

    # Monkeypatch repo backend.get to return stale snapshot to simulate TOCTOU race
    real_get = backend.get

    def fake_get(object_id: str, *path: str):  # type: ignore[override]
        return stale_data, stale_version

    # Swap in fake get just for this call
    monkeypatch.setattr(repo, "_backend", backend)
    monkeypatch.setattr(repo._backend, "get", fake_get)

    with pytest.raises(ConcurrencyError):
        repo.merge_upsert("acct", {"extra": "field"})

    # Restore real get to keep backend consistent for any subsequent tests
    monkeypatch.setattr(repo._backend, "get", real_get)
