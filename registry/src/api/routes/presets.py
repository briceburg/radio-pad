from fastapi import APIRouter

from api.dependencies import DS, AccountId, PageParams, PresetId
from api.errors import NotFoundError
from api.responses import ERROR_404, ERROR_409
from models import (
    AccountStationPreset,
    AccountStationPresetCreate,
    GlobalStationPreset,
    GlobalStationPresetCreate,
    PaginatedList,
)

account_presets = APIRouter(prefix="/accounts/{account_id}/presets", responses=ERROR_404)
global_presets = APIRouter(prefix="/presets", responses=ERROR_404)


@account_presets.put(
    "/{preset_id}",
    response_model=AccountStationPreset,
    response_model_exclude_none=True,
    responses=ERROR_409,
)
async def register_account_preset(
    account_id: AccountId,
    preset_id: PresetId,
    ds: DS,
    preset_data: AccountStationPresetCreate | None = None,
) -> AccountStationPreset:
    partial = preset_data.model_dump(exclude_unset=True) if preset_data else {}
    preset = ds.account_presets.merge_upsert(preset_id, partial, path_params={"account_id": account_id})
    return preset


@account_presets.get("/{preset_id}", response_model=AccountStationPreset, response_model_exclude_none=True)
async def get_account_preset(
    account_id: AccountId,
    preset_id: PresetId,
    ds: DS,
) -> AccountStationPreset:
    preset = ds.account_presets.get(preset_id, path_params={"account_id": account_id})
    if preset is None:
        raise NotFoundError("Station preset not found", details={"account_id": account_id, "preset_id": preset_id})
    return preset


@account_presets.get(
    "",
    response_model=PaginatedList[AccountStationPreset],
    response_model_exclude_none=True,
    include_in_schema=False,
)
@account_presets.get(
    "/",
    response_model=PaginatedList[AccountStationPreset],
    response_model_exclude_none=True,
)
async def list_account_presets(
    account_id: AccountId,
    ds: DS,
    paging: PageParams,
) -> PaginatedList[AccountStationPreset]:
    pl = ds.account_presets.list(path_params={"account_id": account_id}, page=paging.page, per_page=paging.per_page)
    return pl


@global_presets.put(
    "/{preset_id}",
    response_model=GlobalStationPreset,
    response_model_exclude_none=True,
    responses=ERROR_409,
)
async def register_global_preset(
    preset_id: PresetId,
    ds: DS,
    preset_data: GlobalStationPresetCreate | None = None,
) -> GlobalStationPreset:
    partial = preset_data.model_dump(exclude_unset=True) if preset_data else {}
    preset = ds.global_presets.merge_upsert(preset_id, partial)
    return preset


@global_presets.get("/{preset_id}", response_model=GlobalStationPreset, response_model_exclude_none=True)
async def get_global_preset(
    preset_id: PresetId,
    ds: DS,
) -> GlobalStationPreset:
    preset = ds.global_presets.get(preset_id)
    if preset is None:
        raise NotFoundError("Station preset not found", details={"preset_id": preset_id})
    return preset


@global_presets.get(
    "",
    response_model=PaginatedList[GlobalStationPreset],
    response_model_exclude_none=True,
    include_in_schema=False,
)
@global_presets.get(
    "/",
    response_model=PaginatedList[GlobalStationPreset],
    response_model_exclude_none=True,
)
async def list_global_presets(
    ds: DS,
    paging: PageParams,
) -> PaginatedList[GlobalStationPreset]:
    pl = ds.global_presets.list(page=paging.page, per_page=paging.per_page)
    return pl
