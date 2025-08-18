from typing import TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = 1
    per_page: int = 10


class PaginationLinks(BaseModel):
    prev: str | None = None
    next: str | None = None


class PaginatedList[T](BaseModel):
    items: list[T]
    page: int
    per_page: int
    links: PaginationLinks | None = None

    # Derived fields populated post-validation (excluded from serialization)
    has_next: bool = Field(False, exclude=True)
    has_prev: bool = Field(False, exclude=True)
    next_page: int | None = Field(None, exclude=True)
    prev_page: int | None = Field(None, exclude=True)

    @model_validator(mode="after")
    def _compute(self) -> "PaginatedList[T]":
        # "has_next" is true if the number of items returned is equal to the requested page size.
        # This is a common heuristic for cursor-style pagination.
        self.has_next = len(self.items) == self.per_page
        self.has_prev = self.page > 1
        self.next_page = self.page + 1 if self.has_next else None
        self.prev_page = self.page - 1 if self.has_prev else None

        def _qs(p: int) -> str:
            return f"?page={p}&per_page={self.per_page}"

        prev = _qs(self.prev_page) if self.prev_page else None
        nxt = _qs(self.next_page) if self.next_page else None

        self.links = PaginationLinks(prev=prev, next=nxt)
        return self

    @classmethod
    def from_paged(cls, items: list[T], page: int, per_page: int) -> "PaginatedList[T]":
        return cls.model_validate({"items": items, "page": page, "per_page": per_page})
