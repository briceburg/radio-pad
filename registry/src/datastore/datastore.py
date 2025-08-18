import os
from pathlib import Path

from lib.constants import BASE_DIR
from lib.logging import logger

from .backends import LocalBackend, S3Backend
from .core.interfaces import ObjectStore
from .stores.accounts import Accounts
from .stores.players import Players
from .stores.presets import AccountPresets, GlobalPresets


class DataStore:
    """A container for the application's data stores."""

    def __init__(self, data_path: str | None = None, seed_path: str | None = None) -> None:
        # Provide sensible defaults so tests can construct without args
        self.data_path = Path(data_path) if data_path else BASE_DIR / "tmp" / "data"
        self.seed_path = Path(seed_path) if seed_path else BASE_DIR / "data"

        backend_choice = os.environ.get("REGISTRY_BACKEND", "local").lower()
        self.prefix = os.environ.get("REGISTRY_BACKEND_PREFIX", "registry-v1")
        self.backend: ObjectStore
        if backend_choice == "s3":
            bucket = os.environ.get("REGISTRY_BACKEND_S3_BUCKET", "").lower()
            if not bucket:
                raise ValueError("S3 backend selected but REGISTRY_BACKEND_S3_BUCKET is not set")
            self.backend = S3Backend(bucket=bucket, prefix=self.prefix)
        else:
            self.backend = LocalBackend(str(self.data_path), prefix=self.prefix)

        self.accounts = Accounts(self.backend)
        self.players = Players(self.backend)
        self.global_presets = GlobalPresets(self.backend)
        self.account_presets = AccountPresets(self.backend)

    def seed(self) -> None:
        """
        Seeds the datastore with initial data from the data-seed directory.
        Only seeds data if it doesn't already exist in the target datastore.
        """
        import os
        import shutil

        if not self.seed_path.is_dir():
            logger.error(f"Seed path does not exist: {self.seed_path}")
            return

        for dirpath, _, filenames in os.walk(self.seed_path):
            for filename in filenames:
                if not filename.endswith(".json"):
                    continue
                seed_file = Path(dirpath) / filename
                target_base = self.data_path / self.prefix
                target_file = target_base / seed_file.relative_to(self.seed_path)
                if not target_file.exists():
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(seed_file, target_file)
                    logger.info(f"Seeded {target_file}")
