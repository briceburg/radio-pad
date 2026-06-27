from fastapi import APIRouter, Depends

from lib.keys import split_key
from models import Player, PlayerSpec, PlayerSummary

from ..auth import require_account_manager
from ..helpers import ensure_account, get_or_404
from ..models import PaginatedList
from ..responses import ERROR_409
from ..types import DS, AccountId, PageParams, PlayerId

router = APIRouter(prefix="/accounts/{account_id}/players")


@router.put("/{player_id}", response_model=Player, responses=ERROR_409)
async def register_player(
    account_id: AccountId,
    player_id: PlayerId,
    ds: DS,
    player_spec: PlayerSpec,
    _identity: object = Depends(require_account_manager),
) -> Player:
    if player_spec.radio_dial is not None:
        radio_dial_account_id, radio_dial_id = split_key(player_spec.radio_dial)
        get_or_404(
            ds.radio_dials.get(radio_dial_id, path_params={"account_id": radio_dial_account_id}),
            "RadioDial not found",
            radio_dial=player_spec.radio_dial,
        )
    ensure_account(ds, account_id)
    return ds.players.upsert(player_id, player_spec, path_params={"account_id": account_id})


@router.get("/{player_id}", response_model=Player)
async def get_player(
    account_id: AccountId,
    player_id: PlayerId,
    ds: DS,
) -> Player:
    return get_or_404(
        ds.players.get(player_id, path_params={"account_id": account_id}),
        "Player not found",
        account_id=account_id,
        player_id=player_id,
    )


@router.get("/", response_model=PaginatedList[PlayerSummary])
async def list_players(
    account_id: AccountId,
    ds: DS,
    paging: PageParams,
) -> PaginatedList[PlayerSummary]:
    players = ds.players.list(
        path_params={"account_id": account_id},
        page=paging.page,
        per_page=paging.per_page,
    )
    summaries = [PlayerSummary.model_validate(player, from_attributes=True) for player in players]
    return PaginatedList.from_paged(summaries, page=paging.page, per_page=paging.per_page)
