from fastapi import APIRouter

from . import accounts, players, stations

router = APIRouter()

router.include_router(accounts.router, tags=["accounts"])
router.include_router(players.router, tags=["players"])
router.include_router(stations.router, tags=["stations"])
