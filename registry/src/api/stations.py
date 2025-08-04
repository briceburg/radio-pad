from datetime import datetime

from data.store import get_store
from lib.helpers import build_paginated_response, build_response

store = get_store()


async def get(id: str):
    """Returns a StationList - maps to GET /stations/{id}"""

    preset = store.station_presets.get(id)
    if preset is None:
        return {"error": "Station Preset not found"}, 404

    return build_response(preset, "StationList")


async def search(page: int = 1, per_page: int = 10):
    """Returns a paginated StationPresetList - maps to GET /stations"""

    station_presets_list = tuple(
        {"id": k, "lastUpdated": datetime.now().isoformat(timespec="seconds")}
        for k in store.station_presets.keys()
    )

    return build_paginated_response(
        list(station_presets_list), "StationPresetList", page, per_page
    )
