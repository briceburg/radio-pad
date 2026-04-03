from pydantic import BaseModel, Field, HttpUrl, field_validator

from lib.types import Descriptor, Slug, WsUrl
from lib.validators import trim_name


class PlayerBase(BaseModel):
    """Base model for players, containing common fields."""

    name: Descriptor = Field(..., json_schema_extra={"example": "Living Room"})
    stations_url: HttpUrl | None = Field(
        None,
        json_schema_extra={"example": "https://registry.radiopad.dev/api/presets/briceburg"},
    )
    switchboard_url: WsUrl | None = Field(
        None,
        json_schema_extra={"example": "wss://switchboard.radiopad.dev/briceburg/custom-player"},
    )

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        return trim_name(v)


class PlayerCreate(PlayerBase):
    """
    Request body model for creating/updating a player via the PUT endpoint.
    The Player validator provides default station and switchboard URLs.
    """


class PlayerSummary(BaseModel):
    """Abbreviated player model for list endpoints."""

    id: Slug = Field(..., json_schema_extra={"example": "living-room"})
    account_id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
    name: Descriptor = Field(..., json_schema_extra={"example": "Living Room"})


class Player(PlayerBase):
    """The full player model as stored and returned by the API."""

    id: Slug = Field(..., json_schema_extra={"example": "living-room"})
    account_id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
