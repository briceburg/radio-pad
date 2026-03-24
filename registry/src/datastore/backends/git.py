from __future__ import annotations

import fcntl
import io
import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Any, TypeVar, cast

from dulwich import porcelain
from dulwich.errors import GitProtocolError, HangupException, SendPackError
from dulwich.refs import Ref
from dulwich.repo import Repo

from datastore.core import (
    atomic_write_json_file,
    compute_etag,
    construct_storage_path,
    extract_object_id_from_path,
    strip_id,
    validate_if_match,
)
from datastore.exceptions import ConcurrencyError
from datastore.types import JsonDoc, PagedResult, ValueWithETag
from lib.logging import logger

_T = TypeVar("_T")
_RETRY = object()


class GitBackend:
    """Git-backed ObjectStore implementation using a working tree checkout."""

    def __init__(
        self,
        repo_path: str,
        *,
        prefix: str = "",
        branch: str = "main",
        remote_url: str | None = None,
        fetch_ttl_seconds: int = 30,
        author_name: str = "briceburg",
        author_email: str = "briceburg@users.noreply.github.com",
        ssh_key_path: str | None = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.prefix = prefix.strip("/")
        self.branch = branch
        self.remote_url = remote_url
        self.fetch_ttl_seconds = fetch_ttl_seconds
        self.author_name = author_name
        self.author_email = author_email
        self.ssh_key_path = ssh_key_path

        self._head_ref = cast(Ref, b"HEAD")
        self._branch_ref = cast(Ref, f"refs/heads/{self.branch}".encode())
        self._remote_branch_ref = cast(Ref, f"refs/remotes/origin/{self.branch}".encode())
        self._lock = RLock()
        self._lock_path = self.repo_path.parent / f".{self.repo_path.name}.lock"
        self._last_fetch_at = 0.0

        with self._operation_lock():
            self._ensure_repo_exists()
            self._ensure_branch_symbolic_head()
            self._sync_from_remote(force=True)
            repo = self._repo()
            logger.info(
                "Git backend ready: repo=%s branch=%s remote=%s lock=%s fetch_ttl=%ss",
                self.repo_path,
                self.branch,
                self._remote_label(repo),
                self._lock_path,
                self.fetch_ttl_seconds,
            )

    def get(self, object_id: str, *path_parts: str) -> ValueWithETag[JsonDoc]:
        with self._operation_lock():
            self._sync_from_remote(force=False)
            return self._read_existing(self._get_fs_path(object_id, *path_parts))

    def list(self, *path_parts: str, page: int = 1, per_page: int = 10) -> PagedResult[JsonDoc]:
        with self._operation_lock():
            self._sync_from_remote(force=False)
            directory = self._get_dir_path(*path_parts)
            if not directory.exists():
                return []

            files = sorted([p for p in directory.iterdir() if p.suffix == ".json"], key=lambda p: p.stem)
            start = max(0, (page - 1) * per_page)
            page_files = files[start : start + per_page]

            items = [self._read_json_file(file_path) for file_path in page_files]
            for item, file_path in zip(items, page_files, strict=False):
                item["id"] = extract_object_id_from_path(file_path.name)
            return items

    def save(self, object_id: str, data: JsonDoc, *path_parts: str, if_match: str | None = None) -> None:
        with self._operation_lock():
            self._with_write_retry(lambda: self._save_once(object_id, strip_id(data), path_parts, if_match))

    def delete(self, object_id: str, *path_parts: str) -> bool:
        with self._operation_lock():
            return self._with_write_retry(lambda: self._delete_once(object_id, path_parts))

    def _ensure_repo_exists(self) -> None:
        if (self.repo_path / ".git").exists():
            return

        if self.repo_path.exists() and any(self.repo_path.iterdir()):
            raise ValueError(f"Git backend path exists but is not a git checkout: {self.repo_path}")

        if self.remote_url == "":
            raise ValueError(f"Git backend remote disabled but checkout does not exist: {self.repo_path}")

        self.repo_path.parent.mkdir(parents=True, exist_ok=True)
        if self.remote_url:
            remote_url = self.remote_url
            self._run_remote_operation(
                "clone",
                lambda: porcelain.clone(
                    remote_url,
                    str(self.repo_path),
                    checkout=True,
                    branch=self.branch,
                    origin="origin",
                    errstream=io.BytesIO(),
                    **self._auth_kwargs(),
                ),
            )
        else:
            self.repo_path.mkdir(parents=True, exist_ok=True)
            Repo.init(str(self.repo_path))

    def _ensure_branch_symbolic_head(self) -> None:
        repo = self._repo()
        expected = b"ref: " + self._branch_ref
        if repo.refs.read_ref(self._head_ref) == expected:
            return

        if self._branch_ref not in repo.refs.keys():
            try:
                repo.refs[self._branch_ref] = repo.head()
            except KeyError:
                pass

        repo.refs.set_symbolic_ref(self._head_ref, self._branch_ref)

    def _sync_from_remote(self, *, force: bool) -> None:
        repo = self._repo()
        remote_location = self._remote_location(repo)
        if remote_location is None:
            self._last_fetch_at = time.monotonic()
            return

        now = time.monotonic()
        if not force and self.fetch_ttl_seconds > 0 and now - self._last_fetch_at < self.fetch_ttl_seconds:
            return

        self._run_remote_operation(
            "fetch",
            lambda: porcelain.fetch(
                str(self.repo_path),
                remote_location,
                outstream=io.StringIO(),
                errstream=io.BytesIO(),
                quiet=True,
                **self._auth_kwargs(),
            ),
        )

        repo = self._repo()
        if self._remote_branch_ref in repo.refs.keys():
            target = repo.refs[self._remote_branch_ref]
            repo.refs[self._branch_ref] = target
            repo.refs.set_symbolic_ref(self._head_ref, self._branch_ref)
            porcelain.reset(str(self.repo_path), mode="hard", treeish=target)

        self._last_fetch_at = now

    def _push_branch(self) -> bool:
        repo = self._repo()
        remote_location = self._remote_location(repo)
        if remote_location is None:
            return True

        result = self._run_remote_operation(
            "push",
            lambda: porcelain.push(
                str(self.repo_path),
                remote_location,
                refspecs=f"refs/heads/{self.branch}:refs/heads/{self.branch}",
                outstream=io.BytesIO(),
                errstream=io.BytesIO(),
                **self._auth_kwargs(),
            ),
        )
        statuses = result.ref_status or {}
        if any(status is not None for status in statuses.values()):
            self._sync_from_remote(force=True)
            return False

        self._last_fetch_at = time.monotonic()
        return True

    def _save_once(
        self,
        object_id: str,
        data: JsonDoc,
        path_parts: tuple[str, ...],
        if_match: str | None,
    ) -> None | object:
        file_path = self._get_fs_path(object_id, *path_parts)
        current, current_version = self._read_existing(file_path)
        validate_if_match(if_match, current_version)

        if current is not None and compute_etag(data) == current_version:
            return None

        file_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json_file(file_path, data)
        rel_path = self._relative_repo_path(file_path)
        porcelain.add(str(self.repo_path), paths=[rel_path])
        self._commit_change("update", rel_path)
        return None if self._push_branch() else _RETRY

    def _delete_once(self, object_id: str, path_parts: tuple[str, ...]) -> bool | object:
        file_path = self._get_fs_path(object_id, *path_parts)
        if not file_path.exists():
            return False

        rel_path = self._relative_repo_path(file_path)
        porcelain.remove(str(self.repo_path), paths=[rel_path])
        self._prune_empty_dirs(file_path.parent)
        self._commit_change("delete", rel_path)
        return True if self._push_branch() else _RETRY

    def _with_write_retry(self, operation: Callable[[], _T | object]) -> _T:
        for _ in range(2):
            self._sync_from_remote(force=True)
            result = operation()
            if result is not _RETRY:
                return cast(_T, result)
        raise ConcurrencyError("Push rejected")

    @contextmanager
    def _operation_lock(self) -> Iterator[None]:
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._lock_path.open("a+b") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_existing(self, file_path: Path) -> ValueWithETag[JsonDoc]:
        if not file_path.exists():
            return None, None
        raw = self._read_json_file(file_path)
        return raw, compute_etag(raw)

    def _read_json_file(self, file_path: Path) -> dict[str, Any]:
        with file_path.open("r", encoding="utf-8") as f:
            return cast(dict[str, Any], json.load(f))

    def _get_fs_path(self, object_id: str, *path_parts: str) -> Path:
        storage_path = construct_storage_path(prefix=self.prefix, path_parts=path_parts, object_id=object_id)
        return self.repo_path / storage_path

    def _get_dir_path(self, *path_parts: str) -> Path:
        storage_dir = construct_storage_path(prefix=self.prefix, path_parts=path_parts)
        return self.repo_path / storage_dir

    def _relative_repo_path(self, file_path: Path) -> str:
        return file_path.relative_to(self.repo_path).as_posix()

    def _prune_empty_dirs(self, directory: Path) -> None:
        stop = self.repo_path / self.prefix if self.prefix else self.repo_path
        current = directory
        while current != stop and current != self.repo_path and current.exists():
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent

    def _author_identity(self) -> bytes:
        return f"{self.author_name} <{self.author_email}>".encode()

    def _commit_change(self, action: str, rel_path: str) -> None:
        author = self._author_identity()
        porcelain.commit(
            str(self.repo_path),
            message=self._commit_message(action, rel_path),
            author=author,
            committer=author,
        )

    def _commit_message(self, action: str, rel_path: str) -> bytes:
        return f"radio-pad-registry: {action} {rel_path}".encode()

    def _remote_location(self, repo: Repo) -> str | None:
        if self.remote_url == "":
            return None
        if any(ref.startswith(b"refs/remotes/origin/") for ref in repo.refs.keys()):
            return "origin"
        return self.remote_url

    def _remote_label(self, repo: Repo) -> str:
        return self._remote_location(repo) or "disabled"

    def _repo(self) -> Repo:
        return Repo(str(self.repo_path))

    def _run_remote_operation(self, action: str, operation: Callable[[], _T]) -> _T:
        try:
            return operation()
        except (HangupException, GitProtocolError, SendPackError, OSError) as exc:
            raise RuntimeError(self._remote_error_message(action)) from exc

    def _remote_error_message(self, action: str) -> str:
        remote = self.remote_url or "origin"
        message = [
            f"Git backend failed to {action} remote {remote!r} for branch {self.branch!r}.",
        ]
        if self.remote_url and self.remote_url.startswith("git@"):
            message.append("Check SSH auth: ensure REGISTRY_BACKEND_GIT_SSH_KEY_PATH points to a readable private key.")
            message.append(
                "On Fly, set REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY and add the matching public key "
                "to the data repository as a deploy key with write access."
            )
        else:
            message.append("Check remote connectivity and credentials.")
        return " ".join(message)

    def _auth_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.ssh_key_path:
            kwargs["key_filename"] = self.ssh_key_path
        return kwargs
