import json
import os

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


async def get_stations(player_id: str):
    """Get stations for a player - maps to GET /players/{player_id}/stations"""
    if player_id not in PLAYERS:
        return response({"error": "Player not found"}, status=404)

    player_dir = os.path.join(os.path.dirname(__file__), "..", "players", player_id)
    stations_path = os.path.join(player_dir, "stations.json")
    if not os.path.isfile(stations_path):
        return response({"error": "Stations not found"}, status=404)
    try:
        with open(stations_path, "r") as f:
            stations = json.load(f)
        return response(stations, root="stations")
    except Exception:
        return response({"error": "Failed to load stations"}, status=500)


async def search(page: int = 1, per_page: int = 10):
    """List all players - maps to GET /players with pagination"""
    pagination = paginate(PLAYERS_SUMMARY, page, per_page)
    return response(pagination, root="players")
