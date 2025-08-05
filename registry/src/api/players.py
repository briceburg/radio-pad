from fastapi import APIRouter, HTTPException

from data.store import store
from models.pagination import PaginatedList
from models.player import Player, PlayerCreate

router = APIRouter()


@router.put("/players/{account_id}/{id}", response_model=Player)
async def register_player(account_id: str, id: str, player_data: PlayerCreate):
    """Register a player"""
    player_dict = player_data.model_dump(exclude_unset=True)
    store.register_player(account_id, id, player_dict)

    return Player(
        id=id,
        accountId=account_id,
        **player_dict,
    )


@router.get("/players/{account_id}/{id}", response_model=Player)
async def get_player(account_id: str, id: str):
    """Get a player by account and ID"""
    players = store.players.get(account_id, {})
    player_data = players.get(id)
    if player_data is None:
        raise HTTPException(status_code=404, detail="Player not found")

    return Player(
        id=id,
        accountId=account_id,
        **player_data,
    )


@router.get("/players/{account_id}", response_model=PaginatedList[Player])
async def list_players(account_id: str, page: int = 1, per_page: int = 10):
    """List all players for an account"""
    paginated_players = store.get_paginated_players(account_id, page, per_page)
    return PaginatedList(
        items=[
            Player(
                id=id,
                accountId=account_id,
                **p,
            )
            for id, p in paginated_players.items
        ],
        total=paginated_players.total,
        page=paginated_players.page,
        per_page=paginated_players.per_page,
    )
