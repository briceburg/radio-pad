from __future__ import annotations

import io
import json
import time
from pathlib import Path
from threading import RLock
from typing import Any, cast

from dulwich import porcelain
from dulwich.refs import Ref
from dulwich.repo import Repo

from datastore.core import (
    atomic_write_json_file,
    compute_etag,
    construct_storage_path,
    extract_object_id_from_path,
    strip_id,
)
from datastore.exceptions import ConcurrencyError
from datastore.types import JsonDoc, PagedResult, ValueWithETag


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

        self._lock = RLock()
        self._last_fetch_at = 0.0

        with self._lock:
            self._ensure_repo_exists()
            self._ensure_branch_symbolic_head()
            self._sync_from_remote(force=True)

    def get(self, object_id: str, *path_parts: str) -> ValueWithETag[JsonDoc]:
        with self._lock:
            self._sync_from_remote(force=False)
            file_path = self._get_fs_path(object_id, *path_parts)
            if not file_path.exists():
                return None, None
            with file_path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            return raw, compute_etag(raw)

    def list(self, *path_parts: str, page: int = 1, per_page: int = 10) -> PagedResult[JsonDoc]:
        with self._lock:
            self._sync_from_remote(force=False)
            directory = self._get_dir_path(*path_parts)
            if not directory.exists():
                return []

            files = sorted([p for p in directory.iterdir() if p.suffix == ".json"], key=lambda p: p.stem)
            start = max(0, (page - 1) * per_page)
            page_files = files[start : start + per_page]

            items: list[dict[str, Any]] = []
            for file_path in page_files:
                with file_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                data["id"] = extract_object_id_from_path(file_path.name)
                items.append(data)
            return items

    def save(self, object_id: str, data: JsonDoc, *path_parts: str, if_match: str | None = None) -> None:
        with self._lock:
            for attempt in range(2):
                self._sync_from_remote(force=True)
                file_path = self._get_fs_path(object_id, *path_parts)
                current, current_version = self._read_existing(file_path)
                if if_match is not None and if_match != current_version:
                    raise ConcurrencyError("ETag mismatch")

                to_write = strip_id(data)
                if current is not None and compute_etag(to_write) == current_version:
                    return

                file_path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write_json_file(file_path, to_write)
                rel_path = self._relative_repo_path(file_path)
                porcelain.add(str(self.repo_path), paths=[rel_path])
                porcelain.commit(
                    str(self.repo_path),
                    message=self._commit_message("update", rel_path),
                    author=self._author_identity(),
                    committer=self._author_identity(),
                )

                if self._push_branch():
                    return
                if attempt == 1:
                    raise ConcurrencyError("Push rejected")

            raise ConcurrencyError("Push rejected")

    def delete(self, object_id: str, *path_parts: str) -> bool:
        with self._lock:
            for attempt in range(2):
                self._sync_from_remote(force=True)
                file_path = self._get_fs_path(object_id, *path_parts)
                if not file_path.exists():
                    return False

                rel_path = self._relative_repo_path(file_path)
                porcelain.remove(str(self.repo_path), paths=[rel_path])
                self._prune_empty_dirs(file_path.parent)
                porcelain.commit(
                    str(self.repo_path),
                    message=self._commit_message("delete", rel_path),
                    author=self._author_identity(),
                    committer=self._author_identity(),
                )

                if self._push_branch():
                    return True
                if attempt == 1:
                    raise ConcurrencyError("Push rejected")

            raise ConcurrencyError("Push rejected")

    def _ensure_repo_exists(self) -> None:
        if (self.repo_path / ".git").exists():
            return

        if self.repo_path.exists() and any(self.repo_path.iterdir()):
            raise ValueError(f"Git backend path exists but is not a git checkout: {self.repo_path}")

        self.repo_path.parent.mkdir(parents=True, exist_ok=True)
        if self.remote_url:
            porcelain.clone(
                self.remote_url,
                str(self.repo_path),
                checkout=True,
                branch=self.branch,
                origin="origin",
                errstream=io.BytesIO(),
                **self._auth_kwargs(),
            )
        else:
            self.repo_path.mkdir(parents=True, exist_ok=True)
            Repo.init(str(self.repo_path))

    def _ensure_branch_symbolic_head(self) -> None:
        repo = self._repo()
        branch_ref = self._branch_ref()
        expected = b"ref: " + branch_ref
        if repo.refs.read_ref(self._head_ref()) == expected:
            return

        if branch_ref not in repo.refs.keys():
            try:
                repo.refs[branch_ref] = repo.head()
            except KeyError:
                pass

        repo.refs.set_symbolic_ref(self._head_ref(), branch_ref)

    def _sync_from_remote(self, *, force: bool) -> None:
        repo = self._repo()
        remote_location = self._remote_location(repo)
        if remote_location is None:
            self._last_fetch_at = time.monotonic()
            return

        now = time.monotonic()
        if not force and self.fetch_ttl_seconds > 0 and now - self._last_fetch_at < self.fetch_ttl_seconds:
            return

        porcelain.fetch(
            str(self.repo_path),
            remote_location,
            outstream=io.StringIO(),
            errstream=io.BytesIO(),
            quiet=True,
            **self._auth_kwargs(),
        )

        repo = self._repo()
        remote_ref = self._remote_branch_ref()
        if remote_ref in repo.refs.keys():
            target = repo.refs[remote_ref]
            repo.refs[self._branch_ref()] = target
            repo.refs.set_symbolic_ref(self._head_ref(), self._branch_ref())
            porcelain.reset(str(self.repo_path), mode="hard", treeish=target)

        self._last_fetch_at = now

    def _push_branch(self) -> bool:
        repo = self._repo()
        remote_location = self._remote_location(repo)
        if remote_location is None:
            return True

        result = porcelain.push(
            str(self.repo_path),
            remote_location,
            refspecs=f"refs/heads/{self.branch}:refs/heads/{self.branch}",
            outstream=io.BytesIO(),
            errstream=io.BytesIO(),
            **self._auth_kwargs(),
        )
        statuses = result.ref_status or {}
        if any(status is not None for status in statuses.values()):
            self._sync_from_remote(force=True)
            return False

        self._last_fetch_at = time.monotonic()
        return True

    def _read_existing(self, file_path: Path) -> ValueWithETag[JsonDoc]:
        if not file_path.exists():
            return None, None
        with file_path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw, compute_etag(raw)

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

    def _commit_message(self, action: str, rel_path: str) -> bytes:
        return f"{action.title()} {rel_path}".encode()

    def _head_ref(self) -> Ref:
        return cast(Ref, b"HEAD")

    def _branch_ref(self) -> Ref:
        return cast(Ref, f"refs/heads/{self.branch}".encode())

    def _remote_branch_ref(self) -> Ref:
        return cast(Ref, f"refs/remotes/origin/{self.branch}".encode())

    def _remote_location(self, repo: Repo) -> str | None:
        if any(ref.startswith(b"refs/remotes/origin/") for ref in repo.refs.keys()):
            return "origin"
        return self.remote_url or None

    def _repo(self) -> Repo:
        return Repo(str(self.repo_path))

    def _auth_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if self.ssh_key_path:
            kwargs["key_filename"] = self.ssh_key_path
        return kwargs
