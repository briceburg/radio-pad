from fastapi import APIRouter, HTTPException

from data.store import store
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

    return {"stations": preset.get("stations")}


@router.get("/station-presets", response_model=PaginatedList[StationPreset])
async def list_station_presets(page: int = 1, per_page: int = 10):
    """Returns a paginated list of station presets"""
    paginated_presets = store.get_paginated_station_presets(page, per_page)
    return PaginatedList(
        items=[
            StationPreset(
                id=preset.get("id"),
                lastUpdated="2025-08-04T00:00:00",
                stations=StationList(stations=preset.get("stations")),
            )
            for preset in paginated_presets.items
        ],
        total=paginated_presets.total,
        page=paginated_presets.page,
        per_page=paginated_presets.per_page,
    )
