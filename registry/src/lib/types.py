from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, NewType, TypeVar

from pydantic import Field

from lib.constants import SLUG_PATTERN

T = TypeVar("T")

"""Shared type aliases used across datastore and API layers.

Notes on docs and where to define these:
- Keep canonical aliases here (lib/types.py). This module is import-light and stable.
- Let datastore/types.py re-export from here for convenience without becoming the source of truth.
"""

type PagedResult[T] = tuple[list[T], int]
"""Low-level page slice returned by stores: (items, total_count).
Use models.PaginatedList for API responses; this is an internal transport shape.
"""

type ETag = str
"""Opaque entity tag used for optimistic concurrency (HTTP-style ETag)."""

type ValueWithETag[T] = tuple[T | None, ETag | None]
"""Pair (value, etag) as returned by ObjectStore.get; both None when the object doesn't exist."""

type PathParams = Mapping[str, str]
"""Mapping of required path parameters extracted from a path template (e.g., {'account_id': 'a1'})."""

type JsonDoc = dict[str, Any]
"""Opaque JSON object as stored at rest (no reserved fields like 'id')."""


# semantic types (str)
ItemId = NewType("ItemId", str)
ItemId.__doc__ = "Semantic alias for an item identifier within a collection."

PathTemplate = NewType("PathTemplate", str)
PathTemplate.__doc__ = (
    "Path template for a ModelStore, ending with '{id}', optionally containing other placeholders.\n"
    "Example: 'accounts/{account_id}/presets/{id}'."
)

__all__ = [
    "ETag",
    "ItemId",
    "JsonDoc",
    "PageNumber",
    "PagedResult",
    "PathParams",
    "PathTemplate",
    "Slug",
    "ValueWithETag",
    "WsUrl",
]

# Constrained types for Pydantic models and FastAPI params
type Slug = Annotated[
    str,
    Field(
        pattern=SLUG_PATTERN,
        min_length=1,
        max_length=64,
        description="Slug: lowercase letters, numbers, hyphens",
    ),
]
"""Lowercase slug: letters, numbers, and single hyphens (no leading/trailing)."""

type WsUrl = Annotated[str, Field(pattern=r"^(ws|wss)://.+$", description="WebSocket URL (ws:// or wss://)")]
"""WebSocket URL (ws:// or wss://), e.g., 'wss://switchboard.radiopad.dev/briceburg/custom-player'."""

type PageNumber = Annotated[int, Field(ge=1, description="Page number (>=1)")]
"""1-based page number (>= 1)."""
