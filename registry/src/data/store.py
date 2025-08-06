"""
A simple data store for maintaining the available accounts, players, and station presets.
"""

import json
from typing import List, TypeVar

from lib.constants import BASE_DIR
from lib.logging import logger
from models.account import Account
from models.pagination import PaginatedList
from models.player import Player
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
        accounts = [
            Account(id=id, name=account.get("name", id.replace("_", " ").title()))
            for id, account in self.accounts.items()
        ]
        return self._paginate(accounts, page, per_page)

    def get_players(self, account_id: str) -> dict:
        """Return a dictionary of players for a given account."""
        account = self._accounts.get(account_id, {})
        return account.get("players", {})

    def get_player(self, account_id: str, player_id: str) -> dict | None:
        """Return a single player for a given account."""
        return self.get_players(account_id).get(player_id)

    def get_paginated_players(self, account_id: str, page: int, per_page: int):
        """Return a paginated list of players for a given account."""
        players = [
            Player(id=id, accountId=account_id, **p)
            for id, p in self.get_players(account_id).items()
        ]
        return self._paginate(players, page, per_page)

    def get_station_preset(
        self, preset_id: str, account_id: str | None = None
    ) -> StationPreset | None:
        """
        Return a single station preset by its ID.
        If account_id is provided, it only returns the preset if it's owned
        by that account or if it's a global preset.
        """
        preset = self._station_presets.get(preset_id)
        if not preset:
            return None

        # A global preset is always returned
        if preset.account_id is None:
            return preset

        # An account-specific preset is returned only if the account matches
        if account_id and preset.account_id == account_id:
            return preset

        return None

    def get_paginated_station_presets(
        self,
        page: int,
        per_page: int,
        account_id: str | None = None,
        include_globals: bool = False,
    ):
        """
        Return a paginated list of station presets.
        - If account_id is provided, it returns presets for that account.
        - If include_globals is True, it also includes global presets.
        - If account_id is None, it returns only global presets.
        """
        results = []
        if account_id:
            results.extend(
                p for p in self._station_presets.values() if p.account_id == account_id
            )

        if include_globals or not account_id:
            results.extend(
                p for p in self._station_presets.values() if p.account_id is None
            )

        return self._paginate(results, page, per_page)

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
        if account_id:
            preset_data["account_id"] = account_id

        existing_preset = self.get_station_preset(preset_id)
        if existing_preset:
            # Update existing preset
            if "name" in preset_data:
                existing_preset.name = preset_data["name"]
            if "stations" in preset_data:
                existing_preset.stations = [
                    Station(**s) for s in preset_data["stations"]
                ]
            if "account_id" in preset_data:
                existing_preset.account_id = preset_data["account_id"]
            if "category" in preset_data:
                existing_preset.category = preset_data["category"]
            if "description" in preset_data:
                existing_preset.description = preset_data["description"]
            preset = existing_preset
        else:
            # Create new preset
            preset = StationPreset(
                id=preset_id,
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
