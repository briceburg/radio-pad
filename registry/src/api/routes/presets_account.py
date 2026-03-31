from fastapi import APIRouter, Depends

from models import AccountStationPreset, AccountStationPresetCreate, AccountStationPresetSummary

from ..auth import require_account_manager
from ..helpers import get_or_404, get_paginated
from ..models import PaginatedList
from ..responses import ERROR_409
from ..types import DS, AccountId, PageParams, PresetId

router = APIRouter(prefix="/accounts/{account_id}/presets")


@router.put(
    "/{preset_id}",
    response_model=AccountStationPreset,
    response_model_exclude_none=True,
    responses=ERROR_409,
)
async def register_account_preset(
    account_id: AccountId,
    preset_id: PresetId,
    ds: DS,
    preset_data: AccountStationPresetCreate,
    _identity: object = Depends(require_account_manager),
) -> AccountStationPreset:
    preset = ds.account_presets.merge_upsert(preset_id, preset_data, path_params={"account_id": account_id})
    return preset


@router.get("/{preset_id}", response_model=AccountStationPreset, response_model_exclude_none=True)
async def get_account_preset(
    account_id: AccountId,
    preset_id: PresetId,
    ds: DS,
) -> AccountStationPreset:
    return get_or_404(
        ds.account_presets.get(preset_id, path_params={"account_id": account_id}),
        "Station preset not found",
        account_id=account_id,
        preset_id=preset_id,
    )


@router.get(
    "/",
    response_model=PaginatedList[AccountStationPresetSummary],
    response_model_exclude_none=True,
)
async def list_account_presets(
    account_id: AccountId,
    ds: DS,
    paging: PageParams,
) -> PaginatedList[AccountStationPresetSummary]:
    return get_paginated(
        ds.account_presets, AccountStationPresetSummary, paging, path_params={"account_id": account_id}
    )
