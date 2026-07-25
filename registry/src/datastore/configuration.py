from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

from lib.constants import BASE_DIR
from lib.logging import logger

from .backends import GitBackend, LocalBackend, S3Backend
from .core import ObjectStore


@dataclass(frozen=True)
class BackendDefaults:
    path: str
    prefixes: Mapping[str, str]
    prefix_env: str | None
    git_remote_url: str | None


DATA_BACKEND_DEFAULTS = BackendDefaults(
    path=str(BASE_DIR / "tmp" / "data"),
    prefixes={"local": "registry-v1", "s3": "registry-v1", "git": ""},
    prefix_env="REGISTRY_BACKEND_PREFIX",
    git_remote_url="git@github.com:briceburg/radio-pad-registry-data.git",
)

AUTHZ_BACKEND_DEFAULTS = BackendDefaults(
    path=str(BASE_DIR / "tmp" / "authz"),
    prefixes={"local": "registry-authz-v1", "s3": "registry-authz-v1", "git": "registry-authz-v1"},
    prefix_env=None,
    git_remote_url=None,
)


def build_backend_from_env(
    env_prefix: str,
    defaults: BackendDefaults,
    *,
    inherit_from: tuple[str, BackendDefaults] | None = None,
) -> tuple[ObjectStore, str]:
    inherited_env_prefix, inherited_defaults = inherit_from or ("", defaults)
    inherited_backend_choice = os.environ.get(inherited_env_prefix, "local").lower() if inherit_from else "local"
    backend_choice = os.environ.get(env_prefix, inherited_backend_choice).lower()
    if backend_choice not in defaults.prefixes:
        raise ValueError(f"Unsupported {env_prefix} value: {backend_choice}")

    inherits_backend_settings = inherit_from is not None and backend_choice == inherited_backend_choice

    def setting(suffix: str, default: str | None) -> str | None:
        key = f"{env_prefix}_{suffix}"
        if key in os.environ:
            return os.environ[key]
        if inherits_backend_settings:
            return os.environ.get(f"{inherited_env_prefix}_{suffix}", default)
        return default

    def common_git_setting(suffix: str, default: str) -> str:
        common_prefix = inherited_env_prefix if inherit_from else env_prefix
        return os.environ.get(f"{common_prefix}_{suffix}", default)

    prefix = defaults.prefixes[backend_choice]
    if defaults.prefix_env:
        prefix = os.environ.get(defaults.prefix_env, prefix)
    path_default = inherited_defaults.path if inherits_backend_settings else defaults.path
    path = setting("PATH", path_default)
    assert path is not None
    logger.info("%s: %s prefix=%s", env_prefix, backend_choice, prefix)

    if backend_choice == "s3":
        bucket_key = f"{env_prefix}_S3_BUCKET"
        bucket = (setting("S3_BUCKET", "") or "").lower()
        if not bucket:
            raise ValueError(f"S3 backend selected but {bucket_key} is not set")
        return S3Backend(bucket=bucket, prefix=prefix), prefix

    if backend_choice == "git":
        remote_default = inherited_defaults.git_remote_url if inherits_backend_settings else defaults.git_remote_url
        remote_url = setting("GIT_REMOTE_URL", remote_default)
        backend = GitBackend(
            repo_path=path,
            prefix=prefix,
            branch=common_git_setting("GIT_BRANCH", "main"),
            remote_url=remote_url,
            fetch_ttl_seconds=int(common_git_setting("GIT_FETCH_TTL_SECONDS", "30")),
            author_name=common_git_setting("GIT_AUTHOR_NAME", "briceburg"),
            author_email=common_git_setting(
                "GIT_AUTHOR_EMAIL",
                "briceburg@users.noreply.github.com",
            ),
            ssh_key_path=setting("GIT_SSH_KEY_PATH", None),
        )
        return backend, prefix

    return LocalBackend(base_path=path, prefix=prefix), prefix
