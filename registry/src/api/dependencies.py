from typing import Annotated, cast

from fastapi import Depends, HTTPException, Path, Query, Request

from datastore import DataStore
from lib.types import PageNumber, Slug
from models.pagination import PaginationParams

MAX_PER_PAGE = 100


def get_store(request: Request) -> DataStore:
    ds = getattr(request.app.state, "store", None)
    if ds is None or not isinstance(ds, DataStore):
        raise HTTPException(status_code=500, detail="Datastore not initialized")
    return cast(DataStore, ds)


# Typed alias for injecting the DataStore (easy to override in tests via get_store)
DS = Annotated[DataStore, Depends(get_store)]


def pagination(
    page: PageNumber = Query(1, description="Page number (>=1)"),
    per_page: int = Query(10, ge=1, le=MAX_PER_PAGE, description="Items per page (1-100)"),
) -> PaginationParams:
    return PaginationParams(page=page, per_page=per_page)


# Annotated alias for pagination dependency
PageParams = Annotated[PaginationParams, Depends(pagination)]


# Common path param aliases
AccountId = Annotated[Slug, Path(..., description="Account ID (slug)")]
PlayerId = Annotated[Slug, Path(..., description="Player ID (slug)")]
PresetId = Annotated[Slug, Path(..., description="Preset ID (slug)")]


__all__ = [
    "DS",
    "MAX_PER_PAGE",
    "AccountId",
    "PageParams",
    "PlayerId",
    "PresetId",
    "get_store",
    "pagination",
]
