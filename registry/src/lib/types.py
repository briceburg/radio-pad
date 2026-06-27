from typing import Annotated

from pydantic import BeforeValidator, Field

from lib.constants import MAX_DESCRIPTOR_LENGTH, SLUG_PATTERN
from lib.keys import join_key, normalize_call_sign, split_key

_SLUG_PATTERN_BODY = SLUG_PATTERN.removeprefix("^").removesuffix("$")


def _normalize_station_key(value: object) -> str:
    account_id, call_sign = split_key(value)
    return join_key(account_id, normalize_call_sign(call_sign))


def _normalize_radio_dial_key(value: object) -> str:
    account_id, radio_dial_id = split_key(value)
    return join_key(account_id, radio_dial_id)


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
        description="Short display label - max 36 characters",
    ),
]
"""Short display label, such as an account, player, RadioDial, or station name."""

type CallSign = Annotated[
    str,
    BeforeValidator(normalize_call_sign),
    Field(
        pattern=r"^[A-Z0-9](?:[A-Z0-9.-]*[A-Z0-9])?$",
        min_length=1,
        max_length=MAX_DESCRIPTOR_LENGTH,
        description="Canonical uppercase radio station call sign",
    ),
]
"""Canonical uppercase station call sign, unique within an account's stations."""

type StationKey = Annotated[
    str,
    BeforeValidator(_normalize_station_key),
    Field(
        pattern=rf"^{_SLUG_PATTERN_BODY}/[A-Z0-9](?:[A-Z0-9.-]*[A-Z0-9])?$",
        max_length=(MAX_DESCRIPTOR_LENGTH * 2) + 1,
        description="Qualified station key: <account_id>/<CALL_SIGN>",
    ),
]
"""Account-qualified Station identity."""

type RadioDialKey = Annotated[
    str,
    BeforeValidator(_normalize_radio_dial_key),
    Field(
        pattern=rf"^{_SLUG_PATTERN_BODY}/{_SLUG_PATTERN_BODY}$",
        max_length=(MAX_DESCRIPTOR_LENGTH * 2) + 1,
        description="Qualified RadioDial key: <account_id>/<radio_dial_id>",
    ),
]
"""Account-qualified RadioDial identity."""

type WsUrl = Annotated[str, Field(pattern=r"^(ws|wss)://.+$", description="WebSocket URL (ws:// or wss://)")]
"""WebSocket URL (ws:// or wss://), e.g., 'wss://switchboard.radiopad.dev/briceburg/custom-player'."""
