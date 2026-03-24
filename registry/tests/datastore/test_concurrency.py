from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from datastore.backends import LocalBackend
from datastore.core import ModelStore, atomic_write_json_file
from datastore.exceptions import ConcurrencyError
from datastore.types import JsonDoc, ValueWithETag
from models import Account, AccountCreate


def test_merge_upsert_conflict_raises_concurrency_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a write-write race: merge_upsert should pass stale ETag and raise ConcurrencyError."""
    backend = LocalBackend(str(tmp_path))
    repo: ModelStore[Account, AccountCreate] = ModelStore(backend, model=Account, path_template="accounts/{id}")

    # Seed initial value
    repo.save(Account(id="acct", name="One"))

    # Snapshot stale state (data, etag)
    stale_data, stale_version = backend.get("acct", "accounts")
    assert stale_version is not None

    # Concurrent writer updates the document
    backend.save("acct", {"name": "Two"}, "accounts")

    # Monkeypatch repo backend.get to return stale snapshot to simulate TOCTOU race
    real_get = backend.get

    def fake_get(object_id: str, *path: str) -> ValueWithETag[JsonDoc]:
        return stale_data, stale_version

    # Swap in fake get just for this call
    monkeypatch.setattr(repo, "_backend", backend)
    monkeypatch.setattr(repo._backend, "get", fake_get)

    with pytest.raises(ConcurrencyError):
        repo.merge_upsert("acct", AccountCreate(name="Three"))

    # Restore real get to keep backend consistent for any subsequent tests
    monkeypatch.setattr(repo._backend, "get", real_get)


def test_atomic_write_json_file_uses_unique_temp_files_under_concurrency(tmp_path: Path) -> None:
    target = tmp_path / "shared.json"
    errors: list[Exception] = []

    def write_payload(i: int) -> None:
        try:
            atomic_write_json_file(target, {"value": i})
        except Exception as exc:  # pragma: no cover - regression capture
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(write_payload, range(32)))

    assert errors == []
    assert target.exists()
