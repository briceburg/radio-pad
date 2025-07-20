import connexion
from api import create_app, response

app = create_app()


async def get_players():
    return response(app.PLAYERS, root="players")


if __name__ == "__main__":
    from pathlib import Path

    app.run(f"{Path(__file__).stem}:app", port=8080)
