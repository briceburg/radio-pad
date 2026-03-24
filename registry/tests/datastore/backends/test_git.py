from __future__ import annotations

import io
import json
import multiprocessing as mp
import time
from pathlib import Path
from typing import Any, cast

import pytest
from dulwich import porcelain
from dulwich.refs import Ref
from dulwich.repo import Repo

from datastore import DataStore
from datastore.backends.git import GitBackend
from datastore.exceptions import ConcurrencyError

AUTHOR = b"Tests <tests@example.invalid>"
AUTHOR_NAME = "Tests"
AUTHOR_EMAIL = "tests@example.invalid"


def _init_repo(path: Path, *, branch: str = "main") -> None:
    path.mkdir(parents=True, exist_ok=True)
    repo = Repo.init(str(path))
    repo.refs.set_symbolic_ref(cast(Ref, b"HEAD"), cast(Ref, f"refs/heads/{branch}".encode()))


def _commit_json(repo_path: Path, relative_path: str, data: dict[str, object], *, message: bytes) -> None:
    file_path = repo_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    porcelain.add(str(repo_path), paths=[relative_path])
    porcelain.commit(str(repo_path), message=message, author=AUTHOR, committer=AUTHOR)


def _push_main(repo_path: Path, remote_location: str | Path) -> None:
    porcelain.push(
        str(repo_path),
        str(remote_location),
        refspecs="refs/heads/main:refs/heads/main",
        outstream=io.BytesIO(),
        errstream=io.BytesIO(),
    )


def _backend(
    repo_path: Path,
    *,
    branch: str = "main",
    remote_url: str | Path | None = None,
    fetch_ttl_seconds: int = 0,
) -> GitBackend:
    return GitBackend(
        repo_path=str(repo_path),
        remote_url=str(remote_url) if remote_url is not None else None,
        branch=branch,
        fetch_ttl_seconds=fetch_ttl_seconds,
        author_name=AUTHOR_NAME,
        author_email=AUTHOR_EMAIL,
    )


def _contend_for_backend_lock(repo_path: str, ready_conn: Any, result_conn: Any) -> None:
    ready_conn.send("ready")
    ready_conn.recv()

    started = time.monotonic()
    backend = _backend(Path(repo_path))
    with backend._operation_lock():
        result_conn.send(time.monotonic() - started)


def _create_remote_with_seed(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir(parents=True, exist_ok=True)
    Repo.init_bare(str(remote))

    seed = tmp_path / "seed"
    _init_repo(seed)
    _commit_json(seed, "accounts/seed.json", {"name": "Seed"}, message=b"seed")
    _push_main(seed, remote)
    return remote


def test_git_backend_clones_remote_and_reads_seed_data(tmp_path: Path) -> None:
    remote = _create_remote_with_seed(tmp_path)

    backend = _backend(tmp_path / "clone", remote_url=remote)

    data, version = backend.get("seed", "accounts")
    assert data == {"name": "Seed"}
    assert isinstance(version, str) and version


def test_git_backend_refreshes_reads_from_remote(tmp_path: Path) -> None:
    remote = _create_remote_with_seed(tmp_path)
    backend_path = tmp_path / "backend"
    writer_path = tmp_path / "writer"

    porcelain.clone(str(remote), str(backend_path), checkout=True, branch="main")
    porcelain.clone(str(remote), str(writer_path), checkout=True, branch="main")

    backend = _backend(backend_path)

    _commit_json(writer_path, "accounts/fetched.json", {"name": "Fetched"}, message=b"writer update")
    _push_main(writer_path, "origin")

    data, _ = backend.get("fetched", "accounts")
    assert data == {"name": "Fetched"}


def test_git_backend_detects_stale_if_match_after_remote_change(tmp_path: Path) -> None:
    remote = _create_remote_with_seed(tmp_path)
    backend1_path = tmp_path / "backend1"
    backend2_path = tmp_path / "backend2"

    porcelain.clone(str(remote), str(backend1_path), checkout=True, branch="main")
    porcelain.clone(str(remote), str(backend2_path), checkout=True, branch="main")

    backend1 = _backend(backend1_path)
    backend2 = _backend(backend2_path, fetch_ttl_seconds=3600)

    _, stale_version = backend2.get("seed", "accounts")
    assert stale_version is not None

    backend1.save("seed", {"name": "Changed remotely"}, "accounts")

    with pytest.raises(ConcurrencyError, match="ETag mismatch"):
        backend2.save("seed", {"name": "Local stale write"}, "accounts", if_match=stale_version)


def test_git_backend_seeds_empty_repo(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _init_repo(repo_path)
    (repo_path / "LICENSE").write_text("test\n", encoding="utf-8")
    porcelain.add(str(repo_path), paths=["LICENSE"])
    porcelain.commit(str(repo_path), message=b"init", author=AUTHOR, committer=AUTHOR)

    seed_dir = tmp_path / "seed"
    (seed_dir / "accounts").mkdir(parents=True, exist_ok=True)
    (seed_dir / "accounts" / "acct1.json").write_text(json.dumps({"name": "Account One"}), encoding="utf-8")
    (seed_dir / "presets").mkdir(parents=True, exist_ok=True)
    (seed_dir / "presets" / "rock.json").write_text(
        json.dumps({"name": "Rock", "stations": []}),
        encoding="utf-8",
    )

    ds = DataStore(
        backend=_backend(repo_path),
        seed_path=str(seed_dir),
    )
    ds.seed()

    account = ds.accounts.get("acct1")
    assert account is not None
    assert account.name == "Account One"
    assert (repo_path / "accounts" / "acct1.json").exists()
    assert (repo_path / "presets" / "rock.json").exists()


def test_git_backend_repoints_head_to_configured_branch(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _init_repo(repo_path)
    _commit_json(repo_path, "accounts/seed.json", {"name": "Seed"}, message=b"seed")

    repo = Repo(str(repo_path))
    main_ref = cast(Ref, b"refs/heads/main")
    other_ref = cast(Ref, b"refs/heads/other")
    repo.refs[other_ref] = repo.refs[main_ref]
    repo.refs.set_symbolic_ref(cast(Ref, b"HEAD"), other_ref)

    backend = _backend(repo_path)

    backend.save("fresh", {"name": "Fresh"}, "accounts")

    repo = Repo(str(repo_path))
    assert repo.refs.read_ref(cast(Ref, b"HEAD")) == b"ref: refs/heads/main"
    assert repo.refs[main_ref] != repo.refs[other_ref]


def test_git_backend_uses_cross_process_lock_for_shared_repo(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    _init_repo(repo_path)

    backend = _backend(repo_path)
    ctx = mp.get_context("spawn")
    ready_parent, ready_child = ctx.Pipe()
    result_parent, result_child = ctx.Pipe()
    process = ctx.Process(target=_contend_for_backend_lock, args=(str(repo_path), ready_child, result_child))

    with backend._operation_lock():
        process.start()
        assert ready_parent.recv() == "ready"
        ready_parent.send("go")
        time.sleep(0.3)
        assert process.is_alive()
        assert not result_parent.poll()

    assert result_parent.recv() >= 0.3
    process.join(timeout=5)
    assert process.exitcode == 0
