import json
from datetime import datetime
from types import MappingProxyType

from lib.helpers import BASE_DIR, get_logger, paginate
from lib.schema import validate_schema

logger = get_logger()


async def get(id: str):
    """Get a Station Preset by ID - maps to GET /station-presets/{id}"""

    preset = STATION_PRESETS.get(id)
    if preset is None:
        return {"error": "Preset not found"}, 404

    return preset


async def search(page: int = 1, per_page: int = 10):
    """List all station presets - maps to GET /station-presets with pagination"""
    return paginate(STATION_PRESETS_LIST, page, per_page)


def _load_station_presets():
    stations_dir = BASE_DIR / "station-presets"
    station_presets = {}

    for station_file in stations_dir.glob("*.json"):
        with open(station_file, "r") as f:
            stations = json.load(f)
            is_valid, err = validate_schema("StationList", stations)
            if is_valid:
                station_presets[station_file.stem] = stations
            else:
                logger.error(f"Invalid station-presets file: {station_file}: {err}")

    return MappingProxyType(station_presets), tuple(
        {"id": k, "lastUpdated": datetime.now().isoformat(timespec="seconds")}
        for k in station_presets.keys()
    )


STATION_PRESETS, STATION_PRESETS_LIST = _load_station_presets()
