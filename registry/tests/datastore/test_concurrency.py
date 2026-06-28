from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from datastore.backends import LocalBackend
from datastore.core import ModelStore, atomic_write_json_file
from datastore.exceptions import ConcurrencyError
from datastore.types import JsonDoc, ValueWithETag
from models import Account, AccountSpec


def test_upsert_conflict_raises_concurrency_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate a write-write race: upsert should pass a stale ETag and raise ConcurrencyError."""
    backend = LocalBackend(str(tmp_path))
    repo: ModelStore[Account, AccountSpec] = ModelStore(backend, model=Account, path_template="accounts/{id}")

    repo.save(Account(id="acct", name="One"))
    stale_data, stale_version = backend.get("acct", "accounts")
    assert stale_version is not None
    backend.save("acct", {"name": "Two"}, "accounts")

    def fake_get(object_id: str, *path: str) -> ValueWithETag[JsonDoc]:
        return stale_data, stale_version

    monkeypatch.setattr(backend, "get", fake_get)

    with pytest.raises(ConcurrencyError):
        repo.upsert("acct", AccountSpec(name="Three"))


def test_upsert_create_conflict_raises_concurrency_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = LocalBackend(str(tmp_path))
    repo: ModelStore[Account, AccountSpec] = ModelStore(backend, model=Account, path_template="accounts/{id}")
    backend.save("acct", {"name": "Concurrent"}, "accounts")
    monkeypatch.setattr(backend, "get", lambda *args: (None, None))

    with pytest.raises(ConcurrencyError):
        repo.upsert("acct", AccountSpec(name="Requested"))


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
