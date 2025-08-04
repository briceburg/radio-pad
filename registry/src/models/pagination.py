from typing import Generic, List, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedList(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    per_page: int
