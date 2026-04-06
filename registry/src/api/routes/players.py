from fastapi import APIRouter, Depends

from models import Account, Player, PlayerCreate, PlayerSummary

from ..auth import require_account_manager
from ..helpers import get_or_404, get_paginated
from ..models import PaginatedList
from ..responses import ERROR_409
from ..types import DS, AccountId, PageParams, PlayerId

router = APIRouter(prefix="/accounts/{account_id}/players")


@router.put("/{player_id}", response_model=Player, responses=ERROR_409)
async def register_player(
    account_id: AccountId,
    player_id: PlayerId,
    ds: DS,
    player_data: PlayerCreate,
    _identity: object = Depends(require_account_manager),
) -> Player:
    if not ds.accounts.exists(account_id):
        new_account = Account(id=account_id, name=account_id)
        ds.accounts.save(new_account)
    player = ds.players.merge_upsert(player_id, player_data, path_params={"account_id": account_id})
    return player


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
    return get_paginated(ds.players, PlayerSummary, paging, path_params={"account_id": account_id})
