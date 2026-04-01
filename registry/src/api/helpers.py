from typing import Any

from pydantic import BaseModel

from .exceptions import NotFoundError
from .models import PaginatedList


def get_or_404[T](item: T | None, message: str = "Resource not found", **details: str) -> T:
    if item is None:
        raise NotFoundError(message, details=details)
    return item


def paginated_summary[Entity: BaseModel, Summary: BaseModel](
    items: list[Entity],
    summary_model: type[Summary],
    *,
    page: int,
    per_page: int,
) -> PaginatedList[Summary]:
    summaries = [summary_model.model_validate(item, from_attributes=True) for item in items]
    return PaginatedList.from_paged(summaries, page=page, per_page=per_page)


def get_paginated[Entity: BaseModel, Summary: BaseModel](
    store: Any,
    summary_model: type[Summary],
    paging: Any,
    **kwargs: Any,
) -> PaginatedList[Summary]:
    items = store.list(page=paging.page, per_page=paging.per_page, **kwargs)
    return paginated_summary(items, summary_model, page=paging.page, per_page=paging.per_page)
