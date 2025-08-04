from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class PlayerCreate(BaseModel):
    """
    Request body model for creating/updating a player via the PUT endpoint.
    The server will provide default station and switchboard URLs if not provided.
    """

    name: str = Field(..., json_schema_extra={"example": "Living Room"})
    stationsUrl: Optional[HttpUrl] = Field(
        None,
        json_schema_extra={
            "example": "https://registry.radiopad.dev/v1/stations/custom-preset"
        },
    )
    switchboardUrl: Optional[str] = Field(
        None,
        json_schema_extra={
            "example": "wss://switchboard.radiopad.dev/briceburg/custom-player"
        },
    )


class Player(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "living-room"})
    accountId: str = Field(..., json_schema_extra={"example": "briceburg"})
    name: str = Field(..., json_schema_extra={"example": "Living Room"})
    stationsUrl: HttpUrl = Field(
        ...,
        json_schema_extra={
            "example": "https://registry.radiopad.dev/v1/stations/briceburg"
        },
    )
    switchboardUrl: str = Field(
        ...,
        json_schema_extra={
            "example": "wss://switchboard.radiopad.dev/briceburg/living-room"
        },
    )
