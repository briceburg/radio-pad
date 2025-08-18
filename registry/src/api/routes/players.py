from fastapi import APIRouter

from models import Account, Player, PlayerCreate

from ..exceptions import NotFoundError
from ..models import PaginatedList
from ..responses import ERROR_409
from ..types import DS, AccountId, PageParams, PlayerId

router = APIRouter(prefix="/accounts/{account_id}/players")


@router.put("/{player_id}", response_model=Player, responses=ERROR_409)
async def register_player(
    account_id: AccountId,
    player_id: PlayerId,
    ds: DS,
    player_data: PlayerCreate | None = None,
) -> Player:
    if not ds.accounts.exists(account_id):
        new_account = Account(id=account_id, name=account_id)
        ds.accounts.save(new_account)
    partial = player_data.model_dump(exclude_unset=True) if player_data else {}
    player = ds.players.merge_upsert(player_id, partial, path_params={"account_id": account_id})
    return player


@router.get("/{player_id}", response_model=Player)
async def get_player(
    account_id: AccountId,
    player_id: PlayerId,
    ds: DS,
) -> Player:
    player = ds.players.get(player_id, path_params={"account_id": account_id})
    if player is None:
        raise NotFoundError("Player not found", details={"account_id": account_id, "player_id": player_id})
    return player


@router.get("", response_model=PaginatedList[Player], include_in_schema=False)
@router.get("/", response_model=PaginatedList[Player])
async def list_players(
    account_id: AccountId,
    ds: DS,
    paging: PageParams,
) -> PaginatedList[Player]:
    items = ds.players.list(path_params={"account_id": account_id}, page=paging.page, per_page=paging.per_page)
    return PaginatedList.from_paged(items, page=paging.page, per_page=paging.per_page)
