from typing import Annotated, cast

from fastapi import Depends, HTTPException, Path, Query, Request
from pydantic import Field

from datastore import DataStore
from lib.constants import MAX_PER_PAGE
from lib.types import Slug

from .models import PaginationParams

type PageNumber = Annotated[int, Field(ge=1, description="Page number (>=1)")]
"""1-based page number (>= 1)."""


def get_store(request: Request) -> DataStore:
    ds = getattr(request.app.state, "store", None)
    if ds is None or not isinstance(ds, DataStore):
        raise HTTPException(status_code=500, detail="Datastore not initialized")
    return cast(DataStore, ds)


def pagination(
    page: PageNumber = Query(1, description="Page number (>=1)"),
    per_page: int = Query(10, ge=1, le=MAX_PER_PAGE, description="Items per page (1-100)"),
) -> PaginationParams:
    return PaginationParams(page=page, per_page=per_page)


DS = Annotated[DataStore, Depends(get_store)]
PageParams = Annotated[PaginationParams, Depends(pagination)]
AccountId = Annotated[Slug, Path(..., description="Account ID (slug)")]
PlayerId = Annotated[Slug, Path(..., description="Player ID (slug)")]
PresetId = Annotated[Slug, Path(..., description="Preset ID (slug)")]
