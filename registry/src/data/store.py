"""
A simple data store for maintaining the available accounts, players, and station presets.
"""

import json
from typing import List, TypeVar

from lib.constants import BASE_DIR
from lib.logging import logger
from models.pagination import PaginatedList
from models.station_preset import Station, StationPreset

T = TypeVar("T")


class DataStore:
    """A simple data store for maintaining the available accounts, players, and station presets."""

    def __init__(self):
        self._accounts = {
            "briceburg": {
                "players": {
                    "living-room": {"name": "Living Room"},
                    "kitchen": {"name": "Kitchen"},
                }
            },
            "otheruser": {"players": {"office": {"name": "Office"}}},
        }
        self._station_presets: dict[str, StationPreset] = {}
        self.load_station_presets()

    def load_station_presets(self):
        """Load station presets from the station-presets directory."""
        presets_dir = BASE_DIR / "station-presets"
        for preset_file in presets_dir.glob("*.json"):
            with open(preset_file, "r", encoding="utf-8") as f:
                stations_data = json.load(f)
                preset_id = preset_file.stem
                self._station_presets[preset_id] = StationPreset(
                    id=preset_id,
                    name=preset_id.replace("_", " ").title(),
                    stations=[
                        Station(title=s["name"], url=s["url"]) for s in stations_data
                    ],
                )
        logger.info("Loaded %d station presets", len(self._station_presets))

    def _paginate(self, items: List[T], page: int, per_page: int) -> PaginatedList[T]:
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

    def get_players(self, account_id: str) -> dict:
        """Return a dictionary of players for a given account."""
        account = self._accounts.get(account_id, {})
        return account.get("players", {})

    def get_player(self, account_id: str, player_id: str) -> dict | None:
        """Return a single player for a given account."""
        return self.get_players(account_id).get(player_id)

    def get_paginated_players(self, account_id: str, page: int, per_page: int):
        """Return a paginated list of players for a given account."""
        players = self.get_players(account_id)
        return self._paginate(list(players.items()), page, per_page)

    def get_station_preset(self, preset_id: str) -> StationPreset | None:
        """Return a single station preset by its ID."""
        return self._station_presets.get(preset_id)

    def get_paginated_station_presets(
        self, page: int, per_page: int, account_id: str | None = None
    ):
        """
        Return a paginated list of station presets.
        If account_id is provided, it includes global presets and presets
        matching the account_id. Otherwise, only global presets are returned.
        """
        if account_id:
            items = [
                p
                for p in self._station_presets.values()
                if p.account_id is None or p.account_id == account_id
            ]
        else:
            items = [p for p in self._station_presets.values() if p.account_id is None]
        return self._paginate(items, page, per_page)

    def ensure_account(self, account_id: str):
        """Ensures an account exists."""
        if account_id not in self._accounts:
            self._accounts[account_id] = {"players": {}}

    def register_account(self, account_id: str, account_data: dict) -> dict:
        """Registers or updates an account."""
        self.ensure_account(account_id)
        account = self._accounts[account_id]
        account.update(account_data)
        return account

    def register_player(
        self, account_id: str, player_id: str, player_data: dict
    ) -> dict:
        """Registers or updates a player for a given account."""
        self.ensure_account(account_id)

        player = self.get_player(account_id, player_id) or {}
        player.update(player_data)

        self._accounts[account_id]["players"][player_id] = player
        return player

    def register_station_preset(
        self, preset_id: str, preset_data: dict, account_id: str | None = None
    ) -> StationPreset:
        """Registers or updates a station preset."""
        existing_preset = self.get_station_preset(preset_id)
        if existing_preset:
            # Update existing preset
            if "name" in preset_data:
                existing_preset.name = preset_data["name"]
            if "stations" in preset_data:
                existing_preset.stations = [
                    Station(**s) for s in preset_data["stations"]
                ]
            preset = existing_preset
        else:
            # Create new preset
            preset = StationPreset(
                id=preset_id,
                account_id=account_id,
                **preset_data,
            )
        self._station_presets[preset_id] = preset
        return preset


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
