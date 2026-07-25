from __future__ import annotations

import os

from lib.constants import BASE_DIR
from lib.logging import logger

from .backends import GitBackend, LocalBackend, S3Backend
from .core import ObjectStore

_BACKENDS = {"git", "local", "s3"}
DATA_NAMESPACE = "data"
AUTHZ_NAMESPACE = "authz"
_DATA_GIT_REMOTE = "git@github.com:briceburg/radio-pad-registry-data.git"


def data_backend_from_env() -> ObjectStore:
    return _backend_from_env(DATA_NAMESPACE)


def authz_backend_from_env() -> ObjectStore:
    return _backend_from_env(AUTHZ_NAMESPACE)


def _backend_from_env(namespace: str) -> ObjectStore:
    variable = f"REGISTRY_{namespace.upper()}_BACKEND"
    data_backend = _selected_backend("REGISTRY_DATA_BACKEND", "local")
    backend = data_backend if namespace == DATA_NAMESPACE else _selected_backend(variable, data_backend)
    inherit_data = namespace == AUTHZ_NAMESPACE and backend == data_backend

    def setting(suffix: str, default: str | None) -> str | None:
        value = os.environ.get(f"{variable}_{suffix}")
        if value is not None:
            return value
        if inherit_data:
            return os.environ.get(f"REGISTRY_DATA_BACKEND_{suffix}", default)
        return default

    default_path = BASE_DIR / "tmp" / (DATA_NAMESPACE if inherit_data else namespace)
    default_git_remote = _DATA_GIT_REMOTE if namespace == DATA_NAMESPACE or inherit_data else None
    path = setting("PATH", str(default_path))
    assert path is not None
    logger.info("%s backend: %s prefix=%s", namespace.title(), backend, namespace)

    if backend == "local":
        return LocalBackend(base_path=path, prefix=namespace)

    if backend == "s3":
        bucket = setting("S3_BUCKET", None)
        if not bucket:
            raise ValueError("S3 backend selected but no bucket is configured")
        return S3Backend(bucket=bucket.lower(), prefix=namespace)

    return GitBackend(
        repo_path=path,
        prefix=namespace,
        branch=os.environ.get("REGISTRY_GIT_BRANCH", "main"),
        remote_url=setting("GIT_REMOTE_URL", default_git_remote),
        fetch_ttl_seconds=int(os.environ.get("REGISTRY_GIT_FETCH_TTL_SECONDS", "30")),
        author_name=os.environ.get("REGISTRY_GIT_AUTHOR_NAME", "briceburg"),
        author_email=os.environ.get(
            "REGISTRY_GIT_AUTHOR_EMAIL",
            "briceburg@users.noreply.github.com",
        ),
        ssh_key_path=setting("GIT_SSH_KEY_PATH", None),
    )


def _selected_backend(variable: str, default: str) -> str:
    backend = os.environ.get(variable, default).lower()
    if backend not in _BACKENDS:
        raise ValueError(f"Unsupported {variable} value: {backend}")
    return backend
