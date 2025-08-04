from data.store import get_store
from lib.helpers import build_paginated_response, build_response

store = get_store()


async def get(account: str, id: str):
    """Get a player by account and ID - maps to GET /players/{account}/{id}"""
    players = store.players.get(account, {})
    player = players.get(id)
    if player is None:
        return {"error": "Player not found"}, 404

    player = dict(player)
    player["id"] = id
    player["account"] = account

    if not player.get("stationsUrl"):
        player["stationsUrl"] = f"https://registry.radiopad.dev/v1/stations/briceburg"
    if not player.get("switchboardUrl"):
        player["switchboardUrl"] = f"wss://switchboard.radiopad.dev/{account}/{id}"

    return build_response(player, "Player")


async def search(account: str, page: int = 1, per_page: int = 10):
    """List all players for an account - maps to GET /players/{account} with pagination"""
    players = store.players.get(account, {})
    players_list = [{"id": id, "name": p.get("name")} for id, p in players.items()]

    return build_paginated_response(players_list, "PlayerList", page, per_page)
