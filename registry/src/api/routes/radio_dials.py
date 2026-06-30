from fastapi import APIRouter, Depends

from lib.keys import join_key
from models import RadioDial, RadioDialSpec, RadioDialSummary

from ..auth import require_account_owner
from ..helpers import ensure_account, get_or_404
from ..models import PaginatedList
from ..radio_dials import materialize_radio_dial, resolve_station_refs, summarize_radio_dial
from ..responses import ERROR_409
from ..types import DS, AccountId, PageParams, RadioDialId

router = APIRouter(prefix="/accounts/{account_id}/radio-dials")


@router.put(
    "/{radio_dial_id}",
    response_model=RadioDial,
    response_model_exclude_none=True,
    responses=ERROR_409,
)
async def register_radio_dial(
    account_id: AccountId,
    radio_dial_id: RadioDialId,
    ds: DS,
    radio_dial_spec: RadioDialSpec,
    _identity: object = Depends(require_account_owner),
) -> RadioDial:
    stations = resolve_station_refs(ds, radio_dial_spec)
    ensure_account(ds, account_id)
    stored = ds.radio_dials.upsert(
        radio_dial_id,
        radio_dial_spec,
        path_params={"account_id": account_id},
    )
    return materialize_radio_dial(join_key(account_id, radio_dial_id), stored, stations)


@router.get("/{radio_dial_id}", response_model=RadioDial, response_model_exclude_none=True)
async def get_radio_dial(
    account_id: AccountId,
    radio_dial_id: RadioDialId,
    ds: DS,
) -> RadioDial:
    stored = get_or_404(
        ds.radio_dials.get(radio_dial_id, path_params={"account_id": account_id}),
        "RadioDial not found",
        account_id=account_id,
        radio_dial_id=radio_dial_id,
    )
    stations = resolve_station_refs(ds, stored)
    return materialize_radio_dial(join_key(account_id, radio_dial_id), stored, stations)


@router.get("/", response_model=PaginatedList[RadioDialSummary], response_model_exclude_none=True)
async def list_radio_dials(
    account_id: AccountId,
    ds: DS,
    paging: PageParams,
) -> PaginatedList[RadioDialSummary]:
    stored = ds.radio_dials.list(
        path_params={"account_id": account_id},
        page=paging.page,
        per_page=paging.per_page,
    )
    summaries = [
        summarize_radio_dial(join_key(radio_dial.account_id, radio_dial.id), radio_dial) for radio_dial in stored
    ]
    return PaginatedList.from_paged(summaries, page=paging.page, per_page=paging.per_page)
