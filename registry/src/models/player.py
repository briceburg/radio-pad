from pydantic import BaseModel, ConfigDict, Field

from lib.types import Name, RadioDialKey, Slug, WsUrl


class PlayerSpec(BaseModel):
    """Writable player specification without its path-derived identity."""

    model_config = ConfigDict(extra="forbid")

    name: Name = Field(..., json_schema_extra={"example": "Living Room"})
    radio_dial: RadioDialKey | None = Field(
        default=None,
        json_schema_extra={"example": "community/briceburg"},
    )
    switchboard_url: WsUrl | None = Field(
        default=None,
        json_schema_extra={"example": "wss://switchboard.radiopad.dev/briceburg/custom-player"},
    )


class PlayerSummary(BaseModel):
    """Reduced player representation returned by list endpoints."""

    id: Slug = Field(..., json_schema_extra={"example": "living-room"})
    account_id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
    name: Name = Field(..., json_schema_extra={"example": "Living Room"})


class Player(PlayerSpec):
    """The full player model as stored and returned by the API."""

    id: Slug = Field(..., json_schema_extra={"example": "living-room"})
    account_id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
