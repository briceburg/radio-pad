import math
from typing import TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    per_page: int = 10


class PaginationLinks(BaseModel):
    first: str
    last: str
    prev: str | None = None
    next: str | None = None


class PaginatedList[T](BaseModel):
    items: list[T]
    total: int
    page: int
    per_page: int
    links: PaginationLinks | None = None

    # Derived fields populated post-validation (excluded from serialization)
    pages: int = Field(0, exclude=True)
    has_next: bool = Field(False, exclude=True)
    has_prev: bool = Field(False, exclude=True)
    next_page: int | None = Field(None, exclude=True)
    prev_page: int | None = Field(None, exclude=True)

    @model_validator(mode="after")
    def _compute(self) -> "PaginatedList[T]":
        self.pages = math.ceil(self.total / self.per_page) if self.per_page else 0
        self.has_next = self.page < self.pages
        self.has_prev = self.page > 1
        self.next_page = self.page + 1 if self.has_next else None
        self.prev_page = self.page - 1 if self.has_prev else None

        # Build relative links like ?page=X&per_page=Y (doesn't need Request)
        last_page = max(1, self.pages)

        def _qs(p: int) -> str:
            return f"?page={p}&per_page={self.per_page}"

        first = _qs(1)
        last = _qs(last_page)
        # prev: if out-of-bounds high, point to last page; else normal prev when available
        prev: str | None
        if self.page > last_page:
            prev = _qs(last_page)
        elif self.prev_page:
            prev = _qs(self.prev_page)
        else:
            prev = None
        # next: only when within bounds and not on last
        nxt: str | None = _qs(self.page + 1) if self.page < last_page else None

        self.links = PaginationLinks(first=first, last=last, prev=prev, next=nxt)
        return self

    @classmethod
    def from_paged(cls, items: list[T], total: int, page: int, per_page: int) -> "PaginatedList[T]":
        # Use pydantic's model_validate to avoid stricter mypy signature checks
        return cls.model_validate({"items": items, "total": total, "page": page, "per_page": per_page})
