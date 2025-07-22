from api.helpers import response, PLAYERS, PLAYERS_SUMMARY


async def get(player_id):
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


async def search():
    """List all players - maps to GET /players"""
    # TODO: Implement pagination
    return response(PLAYERS_SUMMARY, root="players")
