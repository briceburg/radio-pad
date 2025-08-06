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


class StationPresetBase(BaseModel):
    """Base model for station presets, containing common fields."""

    name: str = Field(..., json_schema_extra={"example": "My Favorite Stations"})
    category: Optional[str] = Field(None, json_schema_extra={"example": "News"})
    description: Optional[str] = Field(
        None,
        json_schema_extra={"example": "A collection of my favorite news stations."},
    )


class StationPresetCreate(StationPresetBase):
    """Request body model for creating/updating a station preset."""

    stations: List[Station]
    account_id: Optional[str] = Field(None, json_schema_extra={"example": "briceburg"})


class StationPresetSummary(StationPresetBase):
    """A summary of a station preset, excluding the list of stations."""

    id: str = Field(..., json_schema_extra={"example": "briceburg"})
    account_id: Optional[str] = Field(None, json_schema_extra={"example": "briceburg"})


class StationPreset(StationPresetSummary):
    """The full station preset model as stored and returned by the API."""

    stations: List[Station]
