import json
from datetime import datetime
from types import MappingProxyType

from lib.constants import BASE_DIR
from lib.helpers import build_paginated_response, build_response, logger
from lib.schema import validate_schema


async def get(id: str):
    """Returns a StationList - maps to GET /stations/{id}"""

    preset = STATION_PRESETS.get(id)
    if preset is None:
        return {"error": "Station Preset not found"}, 404

    return build_response(preset, "StationList")


async def search(page: int = 1, per_page: int = 10):
    """Returns a paginated StationPresetList - maps to GET /stations"""

    return build_paginated_response(
        list(STATION_PRESETS_LIST), "StationPresetList", page, per_page
    )


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
