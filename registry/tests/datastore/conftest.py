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

    def create_stations(self, account_id: str, stations: JsonDoc) -> None:
        account_dir = self.root / "accounts" / account_id
        account_dir.mkdir(parents=True, exist_ok=True)
        (account_dir / "stations.json").write_text(json.dumps(stations))

    def create_radio_dial(self, account_id: str, radio_dial_id: str, name: str, stations: list[str]) -> None:
        radio_dials_dir = self.root / "accounts" / account_id / "radio-dials"
        radio_dials_dir.mkdir(parents=True, exist_ok=True)
        (radio_dials_dir / f"{radio_dial_id}.json").write_text(json.dumps({"name": name, "stations": stations}))
