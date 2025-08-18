from fastapi import APIRouter

from models import AccountStationPreset, AccountStationPresetCreate

from ..exceptions import NotFoundError
from ..models import PaginatedList
from ..responses import ERROR_404, ERROR_409
from ..types import DS, AccountId, PageParams, PresetId

router = APIRouter(prefix="/accounts/{account_id}/presets", responses=ERROR_404)


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
    preset_data: AccountStationPresetCreate | None = None,
) -> AccountStationPreset:
    partial = preset_data.model_dump(exclude_unset=True) if preset_data else {}
    preset = ds.account_presets.merge_upsert(preset_id, partial, path_params={"account_id": account_id})
    return preset


@router.get("/{preset_id}", response_model=AccountStationPreset, response_model_exclude_none=True)
async def get_account_preset(
    account_id: AccountId,
    preset_id: PresetId,
    ds: DS,
) -> AccountStationPreset:
    preset = ds.account_presets.get(preset_id, path_params={"account_id": account_id})
    if preset is None:
        raise NotFoundError("Station preset not found", details={"account_id": account_id, "preset_id": preset_id})
    return preset


@router.get(
    "",
    response_model=PaginatedList[AccountStationPreset],
    response_model_exclude_none=True,
    include_in_schema=False,
)
@router.get(
    "/",
    response_model=PaginatedList[AccountStationPreset],
    response_model_exclude_none=True,
)
async def list_account_presets(
    account_id: AccountId,
    ds: DS,
    paging: PageParams,
) -> PaginatedList[AccountStationPreset]:
    items = ds.account_presets.list(path_params={"account_id": account_id}, page=paging.page, per_page=paging.per_page)
    return PaginatedList.from_paged(items, page=paging.page, per_page=paging.per_page)
