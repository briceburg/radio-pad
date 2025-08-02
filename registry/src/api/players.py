from types import MappingProxyType

from lib.helpers import get_logger, paginate

logger = get_logger()


async def get(id: str):
    """Get a player by ID - maps to GET /players/{id}"""
    player = PLAYERS.get(id)
    if player is None:
        return {"error": "Player not found"}, 404

    player = dict(player)
    player["id"] = id

    if not player.get("stationsUrl"):
        player["stationsUrl"] = (
            f"https://registry.radiopad.dev/v1/players/{id}/stations"
        )
    if not player.get("switchboardUrl"):
        player["switchboardUrl"] = f"wss://{id}.switchboard.radiopad.dev/"

    return player


async def search(page: int = 1, per_page: int = 10):
    """List all players - maps to GET /players with pagination"""
    return paginate(PLAYERS_LIST, page, per_page)


def _load_players():
    # TODO: add player persistence
    players = {}
    return MappingProxyType(players), [
        {"id": id, "name": p.get("name")} for id, p in players.items()
    ]


PLAYERS, PLAYERS_LIST = _load_players()
