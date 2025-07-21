import connexion
from pathlib import Path
import sys
from connexion.options import SwaggerUIOptions
from connexion.middleware import MiddlewarePosition
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import (
    JSONResponse,
    Response,
    PlainTextResponse,
    RedirectResponse,
)
import yaml
import json
import jsonschema
from types import MappingProxyType


class PlayerValidationError(Exception):
    pass


def load_players(players_dir, schema_path):
    players = {}
    with open(schema_path, "r") as f:
        schema = json.load(f)
    for player_file in players_dir.glob("*/player.yaml"):
        with open(player_file, "r") as f:
            player = yaml.safe_load(f)
            try:
                jsonschema.validate(instance=player, schema=schema)
                players[player["id"]] = MappingProxyType(
                    {
                        "id": player.get("id"),
                        "name": player.get("name"),
                        "stationsUrl": player.get("stationsUrl"),
                        "switchboardUrl": player.get("switchboardUrl"),
                    }
                )
            except jsonschema.ValidationError as e:
                raise PlayerValidationError(
                    f"Validation failed for {player_file}: {e.message}"
                )
    return MappingProxyType(players)


def response(data, root="data", status=200):
    accept = connexion.request.headers.get("accept", "")
    if "application/xml" in accept:
        from dicttoxml import dicttoxml

        xml = dicttoxml(
            data, custom_root=root, attr_type=False, item_func=lambda x: x[:-1]
        )
        return Response(content=xml, media_type="application/xml", status_code=status)
    return JSONResponse(data, status_code=status)


def create_app():
    options = SwaggerUIOptions(swagger_ui_path="/api-docs")

    app = connexion.AsyncApp(
        __name__, specification_dir="spec", swagger_ui_options=options
    )
    app.add_api("openapi.yaml", swagger_ui_options=options)
    try:
        app.PLAYERS = load_players(
            Path(__file__).parent / "players",
            Path(__file__).parent / "spec" / "player.schema.json",
        )
        app.PLAYERS_SUMMARY = [
            {"id": p["id"], "name": p["name"]} for p in app.PLAYERS.values()
        ]
    except PlayerValidationError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
    app.add_middleware(
        CORSMiddleware,
        position=MiddlewarePosition.BEFORE_EXCEPTION,
        allow_origins=["*"],
        allow_credentials=False,
    )

    app.add_url_rule(
        "/", "root_redirect", lambda request: RedirectResponse("/v1/api-docs/")
    )

    app.add_url_rule(
        "/healthz",
        "health_check",
        lambda request: PlainTextResponse("ok", status_code=200),
    )
    return app
