from typing import Annotated

from pydantic import Field

from lib.constants import SLUG_PATTERN

# Constrained types for Pydantic models
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
