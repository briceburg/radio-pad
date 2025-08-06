from typing import Optional

from fastapi import APIRouter, HTTPException

from data.store import store
from models.pagination import PaginatedList
from models.station_preset import StationPreset, StationPresetCreate

router = APIRouter()


@router.put("/station-presets/{id}", response_model=StationPreset)
async def register_station_preset(
    id: str, preset_data: StationPresetCreate, account_id: Optional[str] = None
):
    """
    Create or update a station preset.
    If account_id is provided, the preset is associated with that account.
    Only owners should be able to update their presets, but this is not yet enforced.
    """
    preset_dict = preset_data.model_dump(exclude_unset=True)
    preset = store.register_station_preset(id, preset_dict, account_id)
    return preset


@router.get("/station-presets/{id}", response_model=StationPreset)
async def get_station_preset(id: str):
    """Get a single station preset by its ID."""
    preset = store.get_station_preset(id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Station preset not found")
    return preset


@router.get("/station-presets", response_model=PaginatedList[StationPreset])
async def list_station_presets(
    page: int = 1, per_page: int = 10, account_id: Optional[str] = None
):
    """
    List all available station presets.
    If account_id is provided, it includes global presets and presets
    owned by that account.
    """
    paginated_presets = store.get_paginated_station_presets(
        page, per_page, account_id
    )
    return paginated_presets