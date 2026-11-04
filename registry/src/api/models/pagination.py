from pydantic import BaseModel, model_validator


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

    @model_validator(mode="after")
    def _compute(self) -> "PaginatedList[T]":
        def _qs(p: int) -> str:
            return f"?page={p}&per_page={self.per_page}"

        # A full page may have a successor; an empty next page ends traversal.
        self.links = PaginationLinks(
            prev=_qs(self.page - 1) if self.page > 1 else None,
            next=_qs(self.page + 1) if len(self.items) == self.per_page else None,
        )
        return self

    @classmethod
    def from_paged(cls, items: list[T], page: int, per_page: int) -> "PaginatedList[T]":
        return cls.model_validate({"items": items, "page": page, "per_page": per_page})
