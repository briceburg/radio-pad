import os
from pathlib import Path

from lib.constants import BASE_DIR
from lib.logging import logger
from models.account import AccountCreate
from models.player import PlayerCreate
from models.station_preset import AccountStationPresetCreate, GlobalStationPresetCreate

from .backends import GitBackend, LocalBackend, S3Backend
from .core import ObjectStore, SeedableStore, seedable
from .stores import AccountPresets, Accounts, GlobalPresets, Players


class DataStore:
    """A container for the application's data stores."""

    def __init__(
        self,
        backend: ObjectStore | None = None,
        seed_path: str | None = None,
    ) -> None:
        # Provide sensible defaults so tests can construct without args
        self.seed_path = (
            Path(seed_path) if seed_path else Path(os.environ.get("REGISTRY_SEED_PATH", str(BASE_DIR / "data")))
        )

        if backend:
            self.backend = backend
            self.prefix = getattr(backend, "prefix", "")
        else:
            backend_choice = os.environ.get("REGISTRY_BACKEND", "local").lower()
            logger.info(f"DataStore backend: {backend_choice}")
            default_prefix = "" if backend_choice == "git" else "registry-v1"
            self.prefix = os.environ.get("REGISTRY_BACKEND_PREFIX", default_prefix)
            if backend_choice == "s3":
                bucket = os.environ.get("REGISTRY_BACKEND_S3_BUCKET", "").lower()
                if not bucket:
                    raise ValueError("S3 backend selected but REGISTRY_BACKEND_S3_BUCKET is not set")
                self.backend = S3Backend(bucket=bucket, prefix=self.prefix)
            elif backend_choice == "git":
                self.backend = self._build_git_backend()
            else:
                data_path = os.environ.get("REGISTRY_BACKEND_PATH", str(BASE_DIR / "tmp" / "data"))
                self.backend = LocalBackend(base_path=data_path, prefix=self.prefix)

        self.accounts = Accounts(self.backend, create_model=AccountCreate)
        self.players = Players(self.backend, create_model=PlayerCreate)
        self.global_presets = GlobalPresets(self.backend, create_model=GlobalStationPresetCreate)
        self.account_presets = AccountPresets(self.backend, create_model=AccountStationPresetCreate)

    def seed(self) -> None:
        """
        Seeds the datastore with initial data from the data-seed directory.
        Only seeds data if it doesn't already exist in the backend.
        """
        import json

        if not self.seed_path.is_dir():
            logger.error(f"Seed path does not exist: {self.seed_path}")
            return

        # Heterogeneous list of stores; length and order not critical
        stores: list[SeedableStore] = [
            seedable(self.accounts),
            seedable(self.players),
            seedable(self.global_presets),
            seedable(self.account_presets),
        ]

        for dirpath, _, filenames in os.walk(self.seed_path):
            for filename in filenames:
                if not filename.endswith(".json"):
                    continue

                seed_file = Path(dirpath) / filename
                relative_path = str(seed_file.relative_to(self.seed_path))

                for store in stores:
                    if params := store.match(relative_path):
                        object_id = params.pop("id")
                        path_params = params if params else None

                        if store.exists(object_id, path_params=path_params):
                            logger.debug(f"Skipping existing object: {relative_path}")
                            break

                        with seed_file.open("r", encoding="utf-8") as f:
                            data = json.load(f)
                        model_data = {"id": object_id, **params, **data}
                        store.seed(model_data, path_params=path_params)
                        logger.info(f"Seeded {relative_path}")
                        break

    def _build_git_backend(self) -> GitBackend:
        repo_path = os.environ.get("REGISTRY_BACKEND_GIT_REPO_PATH", "/tmp/radio-pad-registry-data")
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
