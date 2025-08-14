from pathlib import Path
import os

from lib import BASE_DIR, logger

from .backends import JSONFileStore, S3FileStore
from .core import ModelStore
from .stores.accounts import Accounts
from .stores.players import Players
from .stores.presets import AccountPresets, GlobalPresets


class DataStore:
    """A container for the application's data stores."""

    def __init__(self, data_path: str | None = None, seed_path: str | None = None) -> None:
        # Provide sensible defaults so tests can construct without args
        self.data_path = Path(data_path) if data_path else BASE_DIR / "tmp" / "data"
        self.seed_path = Path(seed_path) if seed_path else BASE_DIR / "data"
        # Backend selection via env var: DATA_BACKEND in ("json", "s3").
        backend_choice = os.environ.get("DATA_BACKEND", "json").lower()
        if backend_choice == "s3":
            bucket = os.environ.get("S3_BUCKET")
            prefix = os.environ.get("S3_PREFIX", "")
            if not bucket:
                raise ValueError("S3 backend selected but S3_BUCKET is not set")
            self.backend = S3FileStore(bucket=bucket, prefix=prefix)
        else:
            self.backend = JSONFileStore(str(self.data_path))
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
                target_file = self.data_path / seed_file.relative_to(self.seed_path)
                if not target_file.exists():
                    target_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(seed_file, target_file)
                    logger.info(f"Seeded {target_file}")


__all__ = [
    "AccountPresets",
    "Accounts",
    "DataStore",
    "GlobalPresets",
    "JSONFileStore",
    "ModelStore",
    "Players",
]
