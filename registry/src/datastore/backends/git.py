from __future__ import annotations

import fcntl
import json
import os
import shlex
import subprocess
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, TypeVar, cast
from urllib.parse import urlsplit, urlunsplit

from datastore.core import (
    atomic_write_json_file,
    compute_etag,
    construct_storage_path,
    extract_object_id_from_path,
    strip_id,
    validate_write_preconditions,
)
from datastore.exceptions import ConcurrencyError
from datastore.types import JsonDoc, PagedResult, ValueWithETag
from lib.logging import logger

_T = TypeVar("_T")
_RETRY = object()


@dataclass(frozen=True)
class _Remote:
    location: str
    label: str
    url: str | None


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
        self._branch_ref = f"refs/heads/{self.branch}"
        self._remote_branch_ref = f"refs/remotes/origin/{self.branch}"

        self._git_env = os.environ.copy()
        self._git_env.update(
            {
                "GIT_LITERAL_PATHSPECS": "1",
                "GIT_TERMINAL_PROMPT": "0",
                "LC_ALL": "C",
            }
        )
        if self.ssh_key_path and "GIT_SSH_COMMAND" not in self._git_env:
            self._git_env["GIT_SSH_COMMAND"] = (
                f"ssh -i {shlex.quote(self.ssh_key_path)} -o StrictHostKeyChecking=accept-new"
            )

        self._lock = RLock()
        self._lock_path = self.repo_path.parent / f".{self.repo_path.name}.lock"
        self._last_fetch_at = 0.0

        self._validate_branch()

        with self._operation_lock():
            self._ensure_repo_exists()
            self._ensure_branch_symbolic_head()
            self._sync_from_remote(force=True)
            remote = self._resolve_remote()
            logger.info(
                "Git backend ready: repo=%s branch=%s remote=%s lock=%s fetch_ttl=%ss",
                self.repo_path,
                self.branch,
                remote.label if remote else "disabled",
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

    def save(
        self,
        object_id: str,
        data: JsonDoc,
        *path_parts: str,
        if_match: str | None = None,
        if_none_match: bool = False,
    ) -> None:
        with self._operation_lock():
            self._with_write_retry(
                lambda: self._save_once(object_id, strip_id(data), path_parts, if_match, if_none_match)
            )

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
            self._run_git(
                "clone",
                "--quiet",
                "--branch",
                self.branch,
                "--origin",
                "origin",
                "--",
                remote_url,
                str(self.repo_path),
                repo=False,
                remote=_Remote(remote_url, self._display_remote(remote_url), remote_url),
            )
        else:
            self._run_git("init", "--quiet", "--initial-branch", self.branch, str(self.repo_path), repo=False)

    def _ensure_branch_symbolic_head(self) -> None:
        head = self._run_git("symbolic-ref", "--quiet", "HEAD", check=False)
        if head.returncode == 0 and head.stdout.strip() == self._branch_ref:
            return

        if not self._ref_exists(self._branch_ref):
            current_head = self._run_git("rev-parse", "--verify", "--quiet", "HEAD^{commit}", check=False)
            if current_head.returncode == 0:
                self._run_git("branch", self.branch, "HEAD")
            elif current_head.returncode != 1:
                raise RuntimeError(self._git_failure("rev-parse", current_head))

        self._run_git("symbolic-ref", "HEAD", self._branch_ref)

    def _sync_from_remote(self, *, force: bool) -> None:
        remote = self._resolve_remote()
        if remote is None:
            self._last_fetch_at = time.monotonic()
            return

        now = time.monotonic()
        if not force and self.fetch_ttl_seconds > 0 and now - self._last_fetch_at < self.fetch_ttl_seconds:
            logger.debug("Skipping git fetch for %s; within fetch TTL (%ss)", remote.label, self.fetch_ttl_seconds)
            return

        logger.debug("Fetching git remote %s for branch %s", remote.label, self.branch)
        self._run_git(
            "fetch",
            "--quiet",
            "--no-tags",
            "--",
            remote.location,
            f"+refs/heads/{self.branch}:{self._remote_branch_ref}",
            remote=remote,
        )

        self._run_git("symbolic-ref", "HEAD", self._branch_ref)
        self._run_git("reset", "--quiet", "--hard", self._remote_branch_ref)
        target = self._run_git("rev-parse", self._remote_branch_ref).stdout.strip()
        logger.debug("Updated local branch %s to remote target %s", self.branch, target)

        self._last_fetch_at = now

    def _push_branch(self) -> bool:
        remote = self._resolve_remote()
        if remote is None:
            return True

        logger.debug("Pushing git branch %s to %s", self.branch, remote.label)
        result = self._run_git(
            "push",
            "--porcelain",
            "--",
            remote.location,
            f"refs/heads/{self.branch}:refs/heads/{self.branch}",
            remote=remote,
            check=False,
        )

        if result.returncode != 0 and "\t[rejected]" in result.stdout:
            logger.debug("Git push to %s was rejected; refreshing from remote before retry", remote.label)
            self._sync_from_remote(force=True)
            return False
        if result.returncode != 0:
            raise RuntimeError(self._git_failure("push", result, remote))

        self._last_fetch_at = time.monotonic()
        logger.debug("Git push to %s succeeded", remote.label)
        return True

    def _save_once(
        self,
        object_id: str,
        data: JsonDoc,
        path_parts: tuple[str, ...],
        if_match: str | None,
        if_none_match: bool,
    ) -> None | object:
        file_path = self._get_fs_path(object_id, *path_parts)
        current, current_version = self._read_existing(file_path)
        validate_write_preconditions(if_match, if_none_match, current_version)

        if current is not None and compute_etag(data) == current_version:
            return None

        file_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json_file(file_path, data)
        rel_path = self._relative_repo_path(file_path)
        self._run_git("add", "--", rel_path)
        self._commit_change("update", rel_path)
        return None if self._push_branch() else _RETRY

    def _delete_once(self, object_id: str, path_parts: tuple[str, ...]) -> bool | object:
        file_path = self._get_fs_path(object_id, *path_parts)
        if not file_path.exists():
            return False

        rel_path = self._relative_repo_path(file_path)
        self._run_git("rm", "--quiet", "--", rel_path)
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

    def _commit_change(self, action: str, rel_path: str) -> None:
        self._run_git(
            "commit",
            "--quiet",
            "--message",
            self._commit_message(action, rel_path),
            "--",
            rel_path,
            extra_env={
                "GIT_AUTHOR_NAME": self.author_name,
                "GIT_AUTHOR_EMAIL": self.author_email,
                "GIT_COMMITTER_NAME": self.author_name,
                "GIT_COMMITTER_EMAIL": self.author_email,
            },
        )

    def _commit_message(self, action: str, rel_path: str) -> str:
        summary = f"radio-pad-registry: {action} {self._commit_target(rel_path)}"
        return f"{summary}\n\nGenerated-by: radio-pad-registry"

    def _commit_target(self, rel_path: str) -> str:
        parts = Path(rel_path).parts
        if len(parts) == 2 and parts[0] == "accounts":
            return f"account {Path(parts[1]).stem}"
        if len(parts) == 4 and parts[0] == "accounts" and parts[2] == "players":
            return f"player {parts[1]}/{Path(parts[3]).stem}"
        if len(parts) == 3 and parts[0] == "accounts" and parts[2] == "stations.json":
            return f"stations {parts[1]}"
        if len(parts) == 4 and parts[0] == "accounts" and parts[2] == "radio-dials":
            return f"radio dial {parts[1]}/{Path(parts[3]).stem}"
        return rel_path

    def _validate_branch(self) -> None:
        result = self._run_git("check-ref-format", "--branch", self.branch, repo=False, check=False)
        if result.returncode != 0:
            raise ValueError(f"Invalid Git branch name: {self.branch!r}")

    def _ref_exists(self, ref: str) -> bool:
        result = self._run_git("show-ref", "--verify", "--quiet", ref, check=False)
        if result.returncode not in {0, 1}:
            raise RuntimeError(self._git_failure("show-ref", result))
        return result.returncode == 0

    def _resolve_remote(self) -> _Remote | None:
        if self.remote_url == "":
            return None
        origin_url = self._origin_remote_url()
        if origin_url is not None:
            return _Remote("origin", "origin", origin_url)
        if self.remote_url is None:
            return None
        return _Remote(self.remote_url, self._display_remote(self.remote_url), self.remote_url)

    def _run_git(
        self,
        *args: str,
        repo: bool = True,
        remote: _Remote | None = None,
        check: bool = True,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = self._git_env if extra_env is None else self._git_env | extra_env
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repo_path if repo else None,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            message = (
                self._remote_error_message(args[0], remote) if remote else f"Failed to run Git command {args[0]!r}."
            )
            raise RuntimeError(f"{message} Underlying local error: {exc.__class__.__name__}: {exc}") from exc
        if check and result.returncode != 0:
            raise RuntimeError(self._git_failure(args[0], result, remote))
        return result

    def _git_failure(
        self,
        action: str,
        result: subprocess.CompletedProcess[str],
        remote: _Remote | None = None,
    ) -> str:
        message = (
            self._remote_error_message(action, remote)
            if remote
            else f"Git command {action!r} failed with exit status {result.returncode}."
        )
        detail = " | ".join(output.strip() for output in (result.stderr, result.stdout) if output.strip())
        if remote and remote.url:
            detail = detail.replace(remote.url, self._display_remote(remote.url))
        return f"{message} Git reported: {detail}" if detail else message

    def _remote_error_message(self, action: str, remote: _Remote) -> str:
        message = [
            f"Git backend failed to {action} remote {remote.label!r} for branch {self.branch!r}.",
        ]
        if self._is_ssh_remote(remote.url):
            message.append("Check SSH auth: ensure REGISTRY_BACKEND_GIT_SSH_KEY_PATH points to a readable private key.")
            message.append(
                "On Fly, set REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY and add the matching public key "
                "to the data repository as a deploy key with write access."
            )
        else:
            message.append("Check remote connectivity and credentials.")
        return " ".join(message)

    def _origin_remote_url(self) -> str | None:
        result = self._run_git("config", "--get", "remote.origin.url", check=False)
        if result.returncode == 1:
            return None
        if result.returncode != 0:
            raise RuntimeError(self._git_failure("config", result))
        return result.stdout.strip()

    def _display_remote(self, remote_url: str) -> str:
        if "://" in remote_url:
            return self._redacted_url(remote_url)
        scp_target = self._scp_style_target(remote_url)
        if scp_target is not None:
            return scp_target
        return remote_url

    def _is_ssh_remote(self, remote_url: str | None) -> bool:
        if remote_url is None:
            return self.ssh_key_path is not None
        if "://" in remote_url:
            return urlsplit(remote_url).scheme in {"git+ssh", "ssh", "ssh+git"}
        return self._scp_style_target(remote_url) is not None

    def _redacted_url(self, remote_url: str) -> str:
        parsed = urlsplit(remote_url)
        netloc = parsed.hostname or ""
        if parsed.port is not None:
            netloc = f"{netloc}:{parsed.port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))

    def _scp_style_target(self, remote_url: str) -> str | None:
        host, separator, path = remote_url.partition(":")
        if not separator or not host or "/" in host or host.startswith("."):
            return None
        hostname = host.rsplit("@", 1)[-1]
        return f"{hostname}:{path}"
