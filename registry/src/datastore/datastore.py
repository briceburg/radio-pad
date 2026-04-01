import os
from pathlib import Path

from lib.constants import BASE_DIR
from lib.logging import logger

from .backends import GitBackend, LocalBackend, S3Backend
from .core import ObjectStore, SeedableStore, seed_from_path, seedable
from .stores import AccountPresets, Accounts, GlobalPresets, Players


class DataStore:
    """A container for the application's data stores."""

    def __init__(
        self,
        backend: ObjectStore | None = None,
        seed_path: str | None = None,
    ) -> None:
        # Provide sensible defaults so tests can construct without args
        seed_root = Path(os.environ.get("REGISTRY_SEED_DATA_PATH", str(BASE_DIR / "seed-data")))
        self.seed_path = Path(seed_path) if seed_path else seed_root / "store"

        if backend:
            self.backend = backend
            self.prefix = getattr(backend, "prefix", "")
        else:
            backend_choice = os.environ.get("REGISTRY_BACKEND", "local").lower()
            logger.info(f"DataStore backend: {backend_choice}")
            default_prefix = "" if backend_choice == "git" else "registry-v1"
            self.prefix = os.environ.get("REGISTRY_BACKEND_PREFIX", default_prefix)
            data_path = os.environ.get("REGISTRY_BACKEND_PATH", str(BASE_DIR / "tmp" / "data"))
            if backend_choice == "s3":
                bucket = os.environ.get("REGISTRY_BACKEND_S3_BUCKET", "").lower()
                if not bucket:
                    raise ValueError("S3 backend selected but REGISTRY_BACKEND_S3_BUCKET is not set")
                self.backend = S3Backend(bucket=bucket, prefix=self.prefix)
            elif backend_choice == "git":
                self.backend = self._build_git_backend(data_path)
            else:
                self.backend = LocalBackend(base_path=data_path, prefix=self.prefix)

        self.accounts = Accounts(self.backend)
        self.players = Players(self.backend)
        self.global_presets = GlobalPresets(self.backend)
        self.account_presets = AccountPresets(self.backend)

    def seed(self) -> None:
        """
        Seeds the datastore with initial data from the data-seed directory.
        Only seeds data if it doesn't already exist in the backend.
        """
        seed_from_path(self.seed_path, self._seedable_stores(), label="content")

    def _build_git_backend(self, repo_path: str) -> GitBackend:
        remote_url = os.environ.get(
            "REGISTRY_BACKEND_GIT_REMOTE_URL",
            "git@github.com:briceburg/radio-pad-registry-data.git",
        )
        return GitBackend(
            repo_path=repo_path,
            prefix=self.prefix,
            branch=os.environ.get("REGISTRY_BACKEND_GIT_BRANCH", "main"),
            remote_url=remote_url,
            fetch_ttl_seconds=int(os.environ.get("REGISTRY_BACKEND_GIT_FETCH_TTL_SECONDS", "30")),
            author_name=os.environ.get("REGISTRY_BACKEND_GIT_AUTHOR_NAME", "briceburg"),
            author_email=os.environ.get(
                "REGISTRY_BACKEND_GIT_AUTHOR_EMAIL",
                "briceburg@users.noreply.github.com",
            ),
            ssh_key_path=os.environ.get("REGISTRY_BACKEND_GIT_SSH_KEY_PATH"),
        )

    def _seedable_stores(self) -> list[SeedableStore]:
        return [
            seedable(self.accounts),
            seedable(self.players),
            seedable(self.global_presets),
            seedable(self.account_presets),
        ]
