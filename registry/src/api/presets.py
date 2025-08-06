from fastapi import APIRouter, Depends, HTTPException

from data.store import store
from models.pagination import PaginatedList
from models.station_preset import (
    StationPreset,
    StationPresetCreate,
    StationPresetSummary,
)

router = APIRouter()


# Define a shared dependency for pagination parameters
def get_pagination_params(page: int = 1, per_page: int = 10):
    return {"page": page, "per_page": per_page}


@router.put(
    "/accounts/{account_id}/presets/{preset_id}",
    response_model=StationPreset,
    response_model_exclude_none=True,
    tags=["station presets"],
)
async def register_account_preset(
    account_id: str, preset_id: str, preset_data: StationPresetCreate
):
    """Create or update an account station preset."""
    preset_dict = preset_data.model_dump(exclude_unset=True)
    preset = store.register_station_preset(preset_id, preset_dict, account_id)
    return preset


@router.put(
    "/presets/{preset_id}",
    response_model=StationPreset,
    response_model_exclude_none=True,
    tags=["station presets"],
)
async def register_global_preset(preset_id: str, preset_data: StationPresetCreate):
    """Create or update a global station preset."""
    preset_dict = preset_data.model_dump(exclude_unset=True)
    preset = store.register_station_preset(preset_id, preset_dict)
    return preset


@router.get(
    "/accounts/{account_id}/presets/{preset_id}",
    response_model=StationPreset,
    response_model_exclude_none=True,
    tags=["station presets"],
)
async def get_account_preset(account_id: str, preset_id: str):
    """Get a single account station preset by its ID."""
    preset = store.get_station_preset(preset_id, account_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Station preset not found")
    return preset


@router.get(
    "/presets/{preset_id}",
    response_model=StationPreset,
    response_model_exclude_none=True,
    tags=["station presets"],
)
async def get_global_preset(preset_id: str):
    """Get a single global station preset by its ID."""
    preset = store.get_station_preset(preset_id)
    if preset is None:
        raise HTTPException(status_code=404, detail="Station preset not found")
    return preset


@router.get(
    "/accounts/{account_id}/presets",
    response_model=PaginatedList[StationPresetSummary],
    response_model_exclude_none=True,
    tags=["station presets"],
)
async def list_account_presets(
    account_id: str,
    pagination: dict = Depends(get_pagination_params),
    include_globals: bool = False,
):
    """
    List account station presets.
    By default, only presets owned by the account are returned.
    Set `include_globals=true` to include global presets.
    """
    paginated_presets = store.get_paginated_station_presets(
        **pagination, account_id=account_id, include_globals=include_globals
    )
    return paginated_presets


@router.get(
    "/presets",
    response_model=PaginatedList[StationPresetSummary],
    response_model_exclude_none=True,
    tags=["station presets"],
)
async def list_global_presets(pagination: dict = Depends(get_pagination_params)):
    """List all available global station presets."""
    paginated_presets = store.get_paginated_station_presets(**pagination)
    return paginated_presets
