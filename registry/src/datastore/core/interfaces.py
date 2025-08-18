from typing import Any, Protocol, Self

from ..types import JsonDoc, PagedResult, ValueWithETag


class ModelWithId(Protocol):
    id: str

    def model_dump(self, *, mode: str = "json") -> dict[str, Any]: ...

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> Self: ...


class ObjectStore(Protocol):
    def get(self, object_id: str, *path: str) -> ValueWithETag[JsonDoc]: ...

    def list(self, *path: str, page: int = 1, per_page: int = 10) -> PagedResult[JsonDoc]: ...

    def save(self, object_id: str, data: JsonDoc, *path: str, if_match: str | None = None) -> None: ...

    def delete(self, object_id: str, *path: str) -> bool: ...
