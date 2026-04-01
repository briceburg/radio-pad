from collections.abc import Mapping
from typing import Any

type ETag = str
"""Opaque entity tag used for optimistic concurrency (HTTP-style ETag)."""

type JsonDoc = dict[str, Any]
"""Opaque JSON object as stored at rest (no reserved fields like 'id')."""


type PathParams = Mapping[str, str]
"""Mapping of required path parameters extracted from a path template (e.g., {'account_id': 'a1'})."""

type PagedResult[T] = list[T]
"""Low-level page slice returned by stores: a list of items for the current page.
Use models.PaginatedList for API responses; this is an internal transport shape.
"""

type ValueWithETag[T] = tuple[T | None, ETag | None]
"""Pair (value, etag) as returned by ObjectStore.get; both None when the object doesn't exist."""
