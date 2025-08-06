from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class Station(BaseModel):
    """A single station within a preset."""

    title: str = Field(..., json_schema_extra={"example": "WWOZ"})
    url: HttpUrl = Field(
        ..., json_schema_extra={"example": "https://www.wwoz.org/listen/hi"}
    )
    color: Optional[str] = Field(
        default=None,
        pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
        json_schema_extra={"example": "#FF5733"},
    )


class StationPresetCreate(BaseModel):
    """Request body model for creating/updating a station preset."""

    name: str = Field(..., json_schema_extra={"example": "My Favorite Stations"})
    stations: List[Station]


class StationPreset(BaseModel):
    """The full station preset model as stored and returned by the API."""

    id: str = Field(..., json_schema_extra={"example": "briceburg"})
    name: str = Field(..., json_schema_extra={"example": "Briceburg Default"})
    stations: List[Station] 

    # when a preset is missing an account ID, it is considered a global preset
    account_id: Optional[str] = Field(
        None, json_schema_extra={"example": "briceburg"}
    )