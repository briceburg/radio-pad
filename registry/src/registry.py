import connexion
from api import create_app, response

app = create_app()


async def get_player(player_id):
    player = app.PLAYERS.get(player_id)
    if player is None:
        return response({"error": "Player not found"}, status=404)

    if not player.get("stationsUrl"):
        player["stationsUrl"] = (
            f"https://registry.radiopad.dev/players/{player_id}/stations.json"
        )

    if not player.get("switchboardUrl"):
        player["switchboardUrl"] = f"wss://{player_id}.player-switchboard.radiopad.dev"

    return response(player)


async def list_players():
    # TODO: Implement pagination
    players = [{"id": p["id"], "name": p["name"]} for p in app.PLAYERS.values()]
    return response(players, root="players")


if __name__ == "__main__":
    from pathlib import Path

    app.run(f"{Path(__file__).stem}:app", port=8080)
