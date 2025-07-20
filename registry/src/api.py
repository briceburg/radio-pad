import connexion
from pathlib import Path
import sys
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
import yaml
import json
import jsonschema


class PlayerValidationError(Exception):
    pass


def load_players(players_dir, schema_path):
    players = []
    with open(schema_path, "r") as f:
        schema = json.load(f)
    for player_file in players_dir.glob("*/player.yaml"):
        with open(player_file, "r") as f:
            player = yaml.safe_load(f)
            try:
                jsonschema.validate(instance=player, schema=schema)
                players.append({"id": player.get("id"), "name": player.get("name")})
            except jsonschema.ValidationError as e:
                raise PlayerValidationError(
                    f"Validation failed for {player_file}: {e.message}"
                )
    return players


def response(data, root="data"):
    import connexion
    from starlette.responses import JSONResponse, Response

    accept = connexion.request.headers.get("accept", "")
    if "application/xml" in accept:
        from dicttoxml import dicttoxml

        xml = dicttoxml(
            data, custom_root=root, attr_type=False, item_func=lambda x: x[:-1]
        )
        return Response(content=xml, media_type="application/xml")
    return JSONResponse(data)


def create_app():
    app = connexion.AsyncApp(__name__)
    app.add_api("openapi.yaml")
    try:
        app.PLAYERS = load_players(
            Path(__file__).parent / "players",
            Path(__file__).parent / "players" / "player.schema.json",
        )
    except PlayerValidationError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=["*"],
        allow_credentials=False,
    )
    return app
