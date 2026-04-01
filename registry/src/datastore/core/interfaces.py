from typing import Any, Protocol, Self

from ..types import JsonDoc, PagedResult, PathParams, ValueWithETag


class ModelWithId(Protocol):
    id: str

    def model_dump(self, *, mode: str = "json") -> dict[str, Any]: ...

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> Self: ...


class ObjectStore(Protocol):
    """Interface for a versioned, hierarchical object store."""

    def get(self, object_id: str, *path: str) -> ValueWithETag[JsonDoc]: ...

    def list(self, *path: str, page: int = 1, per_page: int = 10) -> PagedResult[JsonDoc]: ...

    def save(self, object_id: str, data: JsonDoc, *path: str, if_match: str | None = None) -> None: ...

    def delete(self, object_id: str, *path: str) -> bool: ...


class SeedableStore(Protocol):
    """Minimal interface used by seeding and helpers to work with stores generically."""

    def match(self, path: str) -> dict[str, str] | None: ...

    def exists(self, object_id: str, *, path_params: PathParams | None = None) -> bool: ...

    def seed(self, data: JsonDoc, *, path_params: PathParams | None = None) -> None: ...
