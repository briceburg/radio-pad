from models.account import Account
from models.player import Player


class AccountStore:
    """A data store for managing accounts and players."""

    def __init__(self, paginate_func):
        self._accounts = {
            "briceburg": {
                "players": {
                    "living-room": {"name": "Living Room"},
                    "kitchen": {"name": "Kitchen"},
                }
            },
            "otheruser": {"players": {"office": {"name": "Office"}}},
        }
        self._paginate = paginate_func

    def list(self, page: int, per_page: int):
        """Return a paginated list of accounts."""
        accounts = [
            Account(id=id, name=account.get("name", id.replace("_", " ").title()))
            for id, account in self._accounts.items()
        ]
        return self._paginate(accounts, page, per_page)

    def _get_raw_players(self, account_id: str) -> dict:
        """Return a dictionary of players for a given account."""
        account = self._accounts.get(account_id, {})
        return account.get("players", {})

    def get_player(self, account_id: str, player_id: str) -> dict | None:
        """Return a single player for a given account."""
        return self._get_raw_players(account_id).get(player_id)

    def list_players(self, account_id: str, page: int, per_page: int):
        """Return a paginated list of players for a given account."""
        players = [
            Player(id=id, accountId=account_id, **p)
            for id, p in self._get_raw_players(account_id).items()
        ]
        return self._paginate(players, page, per_page)

    def ensure(self, account_id: str):
        """Ensures an account exists."""
        if account_id not in self._accounts:
            self._accounts[account_id] = {"players": {}}

    def register(self, account_id: str, account_data: dict) -> dict:
        """Registers or updates an account."""
        self.ensure(account_id)
        account = self._accounts[account_id]
        account.update(account_data)
        return account

    def register_player(
        self, account_id: str, player_id: str, player_data: dict
    ) -> dict:
        """Registers or updates a player for a given account."""
        self.ensure(account_id)

        player = self.get_player(account_id, player_id) or {}
        player.update(player_data)

        self._accounts[account_id]["players"][player_id] = player
        return player
