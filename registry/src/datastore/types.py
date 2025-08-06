from __future__ import annotations

# This module has been consolidated into lib.types.
# Import the public types from lib and re-export them for convenience.
from lib.types import (
    ItemId,
    PathParams,
    PathTemplate,
    JsonDoc,
)

__all__ = [
    "PathParams",
    "JsonDoc",
    "ItemId",
    "PathTemplate",
]
