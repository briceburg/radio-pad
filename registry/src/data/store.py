"""
A simple data store for maintaining the available accounts, players, and station presets.
"""

import json

from lib.constants import BASE_DIR
from lib.helpers import logger


class DataStore:
    """A simple data store for maintaining the available accounts, players, and station presets."""

    def __init__(self):
        self._accounts = {
            "briceburg": {},
            "otheruser": {},
        }
        self._players = {
            "briceburg": {
                "living-room": {"name": "Living Room"},
                "kitchen": {"name": "Kitchen"},
            },
            "otheruser": {"office": {"name": "Office"}},
        }
        self._stations = {}
        self._station_presets = {}

        self.load_station_presets()

    def load_station_presets(self):
        """Load station presets from the station-presets directory."""
        presets_dir = BASE_DIR / "station-presets"
        for preset_file in presets_dir.glob("*.json"):
            with open(preset_file, "r", encoding="utf-8") as f:
                preset = json.load(f)
                self._station_presets[preset_file.stem] = preset
        logger.info("Loaded %d station presets", len(self._station_presets))

    @property
    def accounts(self):
        """Return a dictionary of accounts."""
        return self._accounts

    @property
    def players(self):
        """Return a dictionary of players."""
        return self._players

    @property
    def stations(self):
        """Return a dictionary of stations."""
        return self._stations

    @property
    def station_presets(self):
        """Return a dictionary of station presets."""
        return self._station_presets


_STORE = None


def get_store():
    """Return a singleton instance of the DataStore."""
    global _STORE
    if _STORE is None:
        _STORE = DataStore()
    return _STORE
