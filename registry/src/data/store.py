"""
A simple data store for maintaining the available accounts, players, and station presets.
"""

import json
from typing import List, TypeVar

from lib.constants import BASE_DIR
from lib.logging import logger
from models.pagination import PaginatedList

T = TypeVar("T")




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
                self._station_presets[preset_file.stem] = {
                    "id": preset_file.stem,
                    "stations": preset,
                }
        logger.info("Loaded %d station presets", len(self._station_presets))

    def _paginate(
        self, items: List[T], page: int, per_page: int
    ) -> PaginatedList[T]:
        """Paginates a list of items and returns a PaginatedList model instance."""
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_items = items[start:end]

        return PaginatedList(
            items=paginated_items,
            total=total,
            page=page,
            per_page=per_page,
        )

    @property
    def accounts(self):
        """Return a dictionary of accounts."""
        return self._accounts

    def get_paginated_accounts(self, page: int, per_page: int):
        """Return a paginated list of accounts."""
        return self._paginate(list(self.accounts.items()), page, per_page)

    @property
    def players(self):
        """Return a dictionary of players."""
        return self._players

    def get_paginated_players(self, account_id: str, page: int, per_page: int):
        """Return a paginated list of players for a given account."""
        players = self.players.get(account_id, {})
        return self._paginate(list(players.items()), page, per_page)

    @property
    def stations(self):
        """Return a dictionary of stations."""
        return self._stations

    @property
    def station_presets(self):
        """Return a dictionary of station presets."""
        return self._station_presets

    def get_paginated_station_presets(self, page: int, per_page: int):
        """Return a paginated list of station presets."""
        return self._paginate(list(self.station_presets.values()), page, per_page)

    def register_player(self, account_id: str, player_id: str, player_data: dict):
        """Registers or updates a player for a given account."""
        if account_id not in self._players:
            self._players[account_id] = {}
        self._players[account_id][player_id] = player_data


class StoreProxy:
    """A proxy object that forwards attribute access to the real DataStore."""

    def __init__(self):
        self._store = None

    def initialize(self, store: DataStore):
        """Initializes the proxy with the real DataStore instance."""
        self._store = store

    def __getattr__(self, name):
        if self._store is None:
            raise RuntimeError("DataStore has not been initialized")
        return getattr(self._store, name)


store = StoreProxy()
