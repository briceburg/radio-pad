from __future__ import annotations

import json
import multiprocessing as mp
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from datastore import DataStore
from datastore.backends.git import GitBackend
from datastore.exceptions import ConcurrencyError
from tests.datastore._git_helpers import TEST_IDENTITY, init_repo, run_git

AUTHOR_NAME = "Tests"
AUTHOR_EMAIL = "tests@example.invalid"


def _commit_json(repo_path: Path, relative_path: str, data: dict[str, object], *, message: str) -> None:
    file_path = repo_path / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    run_git("add", "--", relative_path, cwd=repo_path)
    run_git("commit", "--quiet", "--message", message, cwd=repo_path, env=TEST_IDENTITY)


def _push_main(repo_path: Path, remote_location: str | Path) -> None:
    run_git(
        "push",
        "--quiet",
        "--",
        str(remote_location),
        "refs/heads/main:refs/heads/main",
        cwd=repo_path,
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
    init_repo(remote, bare=True)

    seed = tmp_path / "seed"
    init_repo(seed)
    _commit_json(seed, "accounts/seed.json", {"name": "Seed"}, message="seed")
    _push_main(seed, remote)
    return remote


def _clone_pair(tmp_path: Path, remote: Path, *names: str) -> tuple[Path, ...]:
    paths = tuple(tmp_path / name for name in names)
    for path in paths:
        run_git("clone", "--quiet", "--branch", "main", "--", str(remote), str(path), cwd=None)
    return paths


def _patch_git_failure(
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    *,
    error: OSError | None = None,
    stderr: str = "remote operation failed",
) -> None:
    original_run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run

    def failing_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        command = args[0] if args else None
        if isinstance(command, list) and command[:2] == ["git", action]:
            if error:
                raise error
            return subprocess.CompletedProcess(command, 128, stdout="", stderr=stderr)
        return original_run(*args, **kwargs)

    monkeypatch.setattr(subprocess, "run", failing_run)


@pytest.mark.parametrize("remote_path", [r"C:\repo", "C:/repo"])
def test_git_backend_does_not_classify_windows_path_as_ssh_remote(tmp_path: Path, remote_path: str) -> None:
    backend = _backend(tmp_path / "repo")

    assert not backend._is_ssh_remote(remote_path)
    assert backend._display_remote(remote_path) == remote_path


def test_git_backend_clones_remote_and_reads_seed_data(tmp_path: Path) -> None:
    remote = _create_remote_with_seed(tmp_path)

    backend = _backend(tmp_path / "clone", remote_url=remote)

    data, version = backend.get("seed", "accounts")
    assert data == {"name": "Seed"}
    assert isinstance(version, str) and version


def test_git_backend_clone_error_explains_deploy_key_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_git_failure(monkeypatch, "clone")

    with pytest.raises(RuntimeError, match="failed to clone remote") as excinfo:
        _backend(
            tmp_path / "clone",
            remote_url="git@github.com:briceburg/radio-pad-registry-data.git",
        )

    message = str(excinfo.value)
    assert "Git SSH private-key secret" in message
    assert "deploy key with write access" in message


def test_git_backend_clone_error_redacts_remote_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_git_failure(
        monkeypatch,
        "clone",
        stderr="failed to access https://token@github.com/briceburg/radio-pad-registry-data.git",
    )

    with pytest.raises(RuntimeError) as excinfo:
        _backend(
            tmp_path / "clone",
            remote_url="https://token@github.com/briceburg/radio-pad-registry-data.git",
        )

    message = str(excinfo.value)
    assert "token@" not in message
    assert "https://github.com/briceburg/radio-pad-registry-data.git" in message


def test_git_backend_refreshes_reads_from_remote(tmp_path: Path) -> None:
    remote = _create_remote_with_seed(tmp_path)
    backend_path, writer_path = _clone_pair(tmp_path, remote, "backend", "writer")

    backend = _backend(backend_path)

    _commit_json(writer_path, "accounts/fetched.json", {"name": "Fetched"}, message="writer update")
    _push_main(writer_path, "origin")

    data, _ = backend.get("fetched", "accounts")
    assert data == {"name": "Fetched"}


def test_git_backend_origin_ssh_remote_uses_ssh_guidance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    remote = _create_remote_with_seed(tmp_path)
    (backend_path,) = _clone_pair(tmp_path, remote, "backend")

    run_git(
        "config",
        "remote.origin.url",
        "ssh://git@github.com/briceburg/radio-pad-registry-data.git",
        cwd=backend_path,
    )
    _patch_git_failure(monkeypatch, "fetch")

    with pytest.raises(RuntimeError) as excinfo:
        _backend(backend_path)

    assert "Git SSH private-key secret" in str(excinfo.value)


def test_git_backend_explicit_ssh_key_overrides_global_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_path = tmp_path / "repo"
    init_repo(repo_path)
    monkeypatch.setenv("GIT_SSH_COMMAND", "ssh -i /tmp/content-key")

    backend = GitBackend(
        repo_path=str(repo_path),
        remote_url="",
        ssh_key_path="/tmp/authz key",
    )

    assert backend._git_env["GIT_SSH_COMMAND"] == "ssh -i '/tmp/authz key' -o StrictHostKeyChecking=accept-new"


def test_git_backend_clone_oserror_reports_underlying_local_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_git_failure(monkeypatch, "clone", error=OSError("permission denied"))

    with pytest.raises(RuntimeError) as excinfo:
        _backend(
            tmp_path / "clone",
            remote_url="git@github.com:briceburg/radio-pad-registry-data.git",
        )

    assert "Underlying local error: OSError: permission denied" in str(excinfo.value)


def test_git_backend_writes_pretty_json_and_clear_commit_subject(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    init_repo(repo_path)

    backend = _backend(repo_path)
    backend.save(
        "fresh",
        {"name": "Fresh", "stations": ["community/WWOZ"]},
        "accounts",
        "community",
        "radio-dials",
    )

    assert (repo_path / "accounts" / "community" / "radio-dials" / "fresh.json").read_text(encoding="utf-8") == (
        '{\n  "name": "Fresh",\n  "stations": [\n    "community/WWOZ"\n  ]\n}\n'
    )

    assert run_git("log", "-1", "--format=%B", cwd=repo_path).stdout.rstrip() == (
        "radio-pad-registry: update radio dial community/fresh\n\nGenerated-by: radio-pad-registry"
    )


def test_git_backend_detects_stale_if_match_after_remote_change(tmp_path: Path) -> None:
    remote = _create_remote_with_seed(tmp_path)
    backend1_path, backend2_path = _clone_pair(tmp_path, remote, "backend1", "backend2")

    backend1 = _backend(backend1_path)
    backend2 = _backend(backend2_path, fetch_ttl_seconds=3600)

    _, stale_version = backend2.get("seed", "accounts")
    assert stale_version is not None

    backend1.save("seed", {"name": "Changed remotely"}, "accounts")

    with pytest.raises(ConcurrencyError, match="ETag mismatch"):
        backend2.save("seed", {"name": "Local stale write"}, "accounts", if_match=stale_version)


def test_git_backend_can_disable_remote_sync_for_existing_clone(tmp_path: Path) -> None:
    remote = _create_remote_with_seed(tmp_path)
    backend_path, writer_path = _clone_pair(tmp_path, remote, "backend", "writer")

    backend = _backend(backend_path, remote_url="")

    _commit_json(writer_path, "accounts/fetched.json", {"name": "Fetched"}, message="writer update")
    _push_main(writer_path, "origin")

    data, _ = backend.get("fetched", "accounts")
    assert data is None


def test_git_backend_seeds_empty_repo(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    init_repo(repo_path)
    (repo_path / "LICENSE").write_text("test\n", encoding="utf-8")
    run_git("add", "--", "LICENSE", cwd=repo_path)
    run_git("commit", "--quiet", "--message", "init", cwd=repo_path, env=TEST_IDENTITY)

    seed_dir = tmp_path / "seed"
    (seed_dir / "accounts").mkdir(parents=True, exist_ok=True)
    (seed_dir / "accounts" / "acct1.json").write_text(json.dumps({"name": "Account One"}), encoding="utf-8")
    (seed_dir / "accounts" / "acct1" / "radio-dials").mkdir(parents=True, exist_ok=True)
    (seed_dir / "accounts" / "acct1" / "stations.json").write_text(
        json.dumps({"WWOZ": {"stream_url": "https://example.com/wwoz"}}),
        encoding="utf-8",
    )
    (seed_dir / "accounts" / "acct1" / "radio-dials" / "radio.json").write_text(
        json.dumps({"name": "Radio", "stations": ["acct1/WWOZ"]}),
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
    assert (repo_path / "accounts" / "acct1" / "stations.json").exists()
    assert (repo_path / "accounts" / "acct1" / "radio-dials" / "radio.json").exists()


def test_git_backend_repoints_head_to_configured_branch(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    init_repo(repo_path)
    _commit_json(repo_path, "accounts/seed.json", {"name": "Seed"}, message="seed")
    run_git("branch", "other", "main", cwd=repo_path)
    run_git("symbolic-ref", "HEAD", "refs/heads/other", cwd=repo_path)

    backend = _backend(repo_path)

    backend.save("fresh", {"name": "Fresh"}, "accounts")

    assert run_git("symbolic-ref", "HEAD", cwd=repo_path).stdout.strip() == "refs/heads/main"
    assert run_git("rev-parse", "main", cwd=repo_path).stdout != run_git("rev-parse", "other", cwd=repo_path).stdout


def test_git_backend_uses_cross_process_lock_for_shared_repo(tmp_path: Path) -> None:
    repo_path = tmp_path / "repo"
    init_repo(repo_path)

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
