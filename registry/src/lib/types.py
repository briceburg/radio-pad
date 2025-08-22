from typing import Annotated

from pydantic import Field

from lib.constants import MAX_DESCRIPTOR_LENGTH, SLUG_PATTERN

# Constrained types for Pydantic models
type Slug = Annotated[
    str,
    Field(
        pattern=SLUG_PATTERN,
        min_length=1,
        max_length=MAX_DESCRIPTOR_LENGTH,
        description="Slug: lowercase letters, numbers, hyphens",
    ),
]
"""Lowercase slug: letters, numbers, and single hyphens (no leading/trailing)."""

type Descriptor = Annotated[
    str,
    Field(
        max_length=MAX_DESCRIPTOR_LENGTH,
        description="Descriptor field (e.g., name, category) - max 36 characters to allow GUID strings",
    ),
]
"""Constrained string for descriptor fields like names and categories - max 36 characters to allow GUID strings."""

type WsUrl = Annotated[str, Field(pattern=r"^(ws|wss)://.+$", description="WebSocket URL (ws:// or wss://)")]
"""WebSocket URL (ws:// or wss://), e.g., 'wss://switchboard.radiopad.dev/briceburg/custom-player'."""
