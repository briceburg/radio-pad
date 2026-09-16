from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, BrokenBarrierError

import pytest

from datastore.backends import LocalBackend
from datastore.core import ModelStore, atomic_write_json_file
from datastore.exceptions import ConcurrencyError
from datastore.types import JsonDoc, ValueWithETag
from models import Account, AccountSpec


class _CoordinatedLocalBackend(LocalBackend):
    def __init__(self, base_path: str, barrier: Barrier) -> None:
        super().__init__(base_path)
        self._barrier = barrier

    def _read(self, file_path: Path) -> ValueWithETag[JsonDoc]:
        result = super()._read(file_path)
        try:
            self._barrier.wait(timeout=0.5)
        except BrokenBarrierError:
            pass
        return result


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


def test_conditional_writes_are_serialized_across_backend_instances(tmp_path: Path) -> None:
    seed = LocalBackend(str(tmp_path))
    seed.save("acct", {"name": "Original"}, "accounts")
    _, version = seed.get("acct", "accounts")
    assert version is not None

    barrier = Barrier(2)
    backends = [_CoordinatedLocalBackend(str(tmp_path), barrier) for _ in range(2)]

    def save(backend: LocalBackend, name: str) -> bool:
        try:
            backend.save("acct", {"name": name}, "accounts", if_match=version)
        except ConcurrencyError:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        writes = [executor.submit(save, backend, name) for backend, name in zip(backends, ["One", "Two"], strict=True)]

    assert sorted(write.result() for write in writes) == [False, True]
