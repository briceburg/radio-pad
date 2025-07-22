import json
import sys
from pathlib import Path
from types import MappingProxyType

import connexion
import jsonschema
import yaml
from starlette.responses import JSONResponse, Response

BASE_DIR = Path(__file__).parent.parent


def paginate(items, page=1, per_page=10, max_per_page=100):
    """Paginate a list of items, returning a dict with items and metadata."""
    try:
        page = int(page)
        per_page = int(per_page)
    except (ValueError, TypeError):
        page = 1
        per_page = 10

    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 10
    if per_page > max_per_page:
        per_page = max_per_page

    total = len(items)
    start = (page - 1) * per_page
    end = start + per_page
    paged_items = items[start:end]
    return {
        "items": paged_items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": (total + per_page - 1) // per_page,
    }


def response(data, root="data", status=200):
    """Return a JSON or XML response based on Accept header."""
    accept = connexion.request.headers.get("accept", "")
    if "application/xml" in accept:
        from dicttoxml import dicttoxml

        xml = dicttoxml(
            data, custom_root=root, attr_type=False, item_func=lambda x: x[:-1]
        )
        return Response(content=xml, media_type="application/xml", status_code=status)
    return JSONResponse(data, status_code=status)


def _load_players(players_dir: Path, schema_path: Path):
    """Load and validate all player definitions."""
    with open(schema_path, "r") as schema_file:
        schema = json.load(schema_file)

    players = {}
    for player_file in players_dir.glob("*/player.yaml"):
        with open(player_file, "r") as f:
            player = yaml.safe_load(f)
        jsonschema.validate(instance=player, schema=schema)
        players[player["id"]] = {
            "id": player.get("id"),
            "name": player.get("name"),
            "stationsUrl": player.get("stationsUrl"),
            "switchboardUrl": player.get("switchboardUrl"),
        }
    return MappingProxyType(players)


# Load PLAYERS and PLAYERS_SUMMARY _once_ at import time
try:
    PLAYERS = _load_players(
        BASE_DIR / "players", BASE_DIR / "spec" / "player.schema.json"
    )
    PLAYERS_SUMMARY = [{"id": p["id"], "name": p["name"]} for p in PLAYERS.values()]
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
