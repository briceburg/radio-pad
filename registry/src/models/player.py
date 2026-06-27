from pydantic import BaseModel, ConfigDict, Field, field_validator

from lib.types import Descriptor, RadioDialKey, Slug, WsUrl
from lib.validators import trim_name


class PlayerSpec(BaseModel):
    """Writable player specification without its path-derived identity."""

    model_config = ConfigDict(extra="forbid")

    name: Descriptor = Field(..., json_schema_extra={"example": "Living Room"})
    radio_dial: RadioDialKey | None = Field(
        default=None,
        json_schema_extra={"example": "community/briceburg"},
    )
    switchboard_url: WsUrl | None = Field(
        default=None,
        json_schema_extra={"example": "wss://switchboard.radiopad.dev/briceburg/custom-player"},
    )

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        return trim_name(v)


class PlayerSummary(BaseModel):
    """Reduced player representation returned by list endpoints."""

    id: Slug = Field(..., json_schema_extra={"example": "living-room"})
    account_id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
    name: Descriptor = Field(..., json_schema_extra={"example": "Living Room"})


class Player(PlayerSpec):
    """The full player model as stored and returned by the API."""

    id: Slug = Field(..., json_schema_extra={"example": "living-room"})
    account_id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
