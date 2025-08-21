import json
from pathlib import Path

import pytest

from datastore.types import JsonDoc


@pytest.fixture
def temp_data_path(tmp_path: Path) -> Path:
    """Creates a temporary data path for datastore tests."""
    data_path = tmp_path / "data"
    data_path.mkdir()
    return data_path


class SeedCreator:
    """Helper for creating seed data directories and files for tests."""

    def __init__(self, root: Path):
        self.root = root

    def create_account(self, account_id: str, name: str) -> None:
        accounts_dir = self.root / "accounts"
        accounts_dir.mkdir(parents=True, exist_ok=True)
        (accounts_dir / f"{account_id}.json").write_text(json.dumps({"name": name}))

    def create_global_preset(self, preset_id: str, name: str, stations: list[JsonDoc] | None = None) -> None:
        presets_dir = self.root / "presets"
        presets_dir.mkdir(parents=True, exist_ok=True)
        (presets_dir / f"{preset_id}.json").write_text(json.dumps({"name": name, "stations": stations or []}))
