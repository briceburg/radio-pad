from api.helpers import PLAYERS, PLAYERS_SUMMARY, paginate, response


async def get(player_id: str):
    """Get a player by ID - maps to GET /players/{player_id}"""
    player = PLAYERS.get(player_id)
    if player is None:
        return response({"error": "Player not found"}, status=404)

    # Make a shallow copy for fallback fields
    player = dict(player)

    if not player.get("stationsUrl"):
        player["stationsUrl"] = (
            f"https://registry.radiopad.dev/players/{player_id}/stations.json"
        )

    if not player.get("switchboardUrl"):
        player["switchboardUrl"] = f"wss://{player_id}.player-switchboard.radiopad.dev"

    return response(player, root="player")


async def search(page: int = 1, per_page: int = 10):
    """List all players - maps to GET /players with pagination"""
    pagination = paginate(PLAYERS_SUMMARY, page, per_page)
    return response(pagination, root="players")
