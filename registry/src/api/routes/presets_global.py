from fastapi import APIRouter, Depends

from models import GlobalStationPreset, GlobalStationPresetCreate, GlobalStationPresetSummary

from ..auth import require_admin
from ..exceptions import NotFoundError
from ..helpers import paginated_summary
from ..models import PaginatedList
from ..responses import ERROR_409
from ..types import DS, PageParams, PresetId

router = APIRouter(prefix="/presets")


@router.put(
    "/{preset_id}",
    response_model=GlobalStationPreset,
    response_model_exclude_none=True,
    responses=ERROR_409,
)
async def register_global_preset(
    preset_id: PresetId,
    ds: DS,
    preset_data: GlobalStationPresetCreate,
    _identity: object = Depends(require_admin),
) -> GlobalStationPreset:
    preset = ds.global_presets.merge_upsert(preset_id, preset_data)
    return preset


@router.get("/{preset_id}", response_model=GlobalStationPreset, response_model_exclude_none=True)
async def get_global_preset(
    preset_id: PresetId,
    ds: DS,
) -> GlobalStationPreset:
    preset = ds.global_presets.get(preset_id)
    if preset is None:
        raise NotFoundError("Station preset not found", details={"preset_id": preset_id})
    return preset


@router.get(
    "/",
    response_model=PaginatedList[GlobalStationPresetSummary],
    response_model_exclude_none=True,
)
async def list_global_presets(
    ds: DS,
    paging: PageParams,
) -> PaginatedList[GlobalStationPresetSummary]:
    items = ds.global_presets.list(page=paging.page, per_page=paging.per_page)
    return paginated_summary(items, GlobalStationPresetSummary, page=paging.page, per_page=paging.per_page)
