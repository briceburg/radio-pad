from typing import Annotated

from fastapi import APIRouter, Depends, Path

from lib.types import CallSign
from models import Station, StationSpec

from ..auth import require_account_manager
from ..helpers import ensure_account, get_or_404
from ..models import PaginatedList
from ..responses import ERROR_409
from ..types import DS, AccountId, PageParams

router = APIRouter(prefix="/accounts/{account_id}/stations")


@router.put("/{call_sign}", response_model=Station, response_model_exclude_none=True, responses=ERROR_409)
async def register_station(
    account_id: AccountId,
    call_sign: Annotated[CallSign, Path(..., description="Canonical station call sign")],
    ds: DS,
    station_spec: StationSpec,
    _identity: object = Depends(require_account_manager),
) -> Station:
    ensure_account(ds, account_id)
    return ds.stations.upsert(account_id, call_sign, station_spec)


@router.get("/{call_sign}", response_model=Station, response_model_exclude_none=True)
async def get_station(
    account_id: AccountId,
    call_sign: Annotated[CallSign, Path(..., description="Canonical station call sign")],
    ds: DS,
) -> Station:
    return get_or_404(
        ds.stations.get(account_id, call_sign),
        "Station not found",
        account_id=account_id,
        call_sign=call_sign,
    )


@router.get("/", response_model=PaginatedList[Station], response_model_exclude_none=True)
async def list_stations(account_id: AccountId, ds: DS, paging: PageParams) -> PaginatedList[Station]:
    stations = ds.stations.list(account_id, page=paging.page, per_page=paging.per_page)
    return PaginatedList.from_paged(stations, page=paging.page, per_page=paging.per_page)
