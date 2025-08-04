from fastapi import APIRouter, HTTPException

from data.store import store
from lib.pagination import paginate
from models.pagination import PaginatedList
from models.station import StationList
from models.station_preset import StationPreset

router = APIRouter()


@router.get("/stations/{id}", response_model=StationList)
async def get_station_list(id: str):
    """Returns a StationList"""
    preset = store.station_presets.get(id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Station Preset not found")

    return {"stations": preset}


@router.get("/station-presets", response_model=PaginatedList[StationPreset])
async def list_station_presets(page: int = 1, per_page: int = 10):
    """Returns a paginated list of station presets"""
    presets = [
        StationPreset(
            id=id,
            lastUpdated="2025-08-04T00:00:00",
            stations=StationList(stations=stations),
        )
        for id, stations in store.station_presets.items()
    ]
    return paginate(presets, page, per_page)
