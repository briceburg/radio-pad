import os
from pathlib import Path

from lib.constants import BASE_DIR

from .configuration import DATA_BACKEND_DEFAULTS, build_backend_from_env
from .core import ObjectStore, SeedableStore, seed_from_path, seedable
from .stores import Accounts, Players, RadioDials, Stations


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
            self.backend, self.prefix = build_backend_from_env("REGISTRY_BACKEND", DATA_BACKEND_DEFAULTS)

        self.accounts = Accounts(self.backend)
        self.players = Players(self.backend)
        self.stations = Stations(self.backend)
        self.radio_dials = RadioDials(self.backend)

    def seed(self) -> None:
        """
        Seeds the datastore with initial data from the data-seed directory.
        Only seeds data if it doesn't already exist in the backend.
        """
        seed_from_path(self.seed_path, self._seedable_stores(), label="content")

    def _seedable_stores(self) -> list[SeedableStore]:
        return [
            seedable(self.accounts),
            seedable(self.players),
            self.stations,
            seedable(self.radio_dials),
        ]
