from pydantic import BaseModel, Field, HttpUrl, model_validator

from lib.types import Slug


class Station(BaseModel):
    """A single station within a preset."""

    name: str = Field(..., json_schema_extra={"example": "WWOZ"})
    url: HttpUrl = Field(..., json_schema_extra={"example": "https://www.wwoz.org/listen/hi"})
    color: str | None = Field(
        default=None,
        pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
        json_schema_extra={"example": "#FF5733"},
    )


class StationPresetBase(BaseModel):
    """Base model for station presets, containing common fields."""

    name: str = Field(..., json_schema_extra={"example": "My Favorite Stations"})
    category: str | None = Field(None, json_schema_extra={"example": "News"})
    description: str | None = Field(
        None,
        json_schema_extra={"example": "A collection of my favorite news stations."},
    )
    stations: list[Station]

    @model_validator(mode="after")
    def _ensure_unique_station_fields(self) -> "StationPresetBase":
        seen_names: set[str] = set()
        seen_urls: set[str] = set()
        for st in self.stations:
            name = st.name.strip().lower()
            url = str(st.url).strip().lower()
            if name in seen_names:
                raise ValueError(f"Duplicate station name: {st.name}")
            if url in seen_urls:
                raise ValueError(f"Duplicate station URL: {st.url}")
            seen_names.add(name)
            seen_urls.add(url)
        return self


class GlobalStationPresetCreate(StationPresetBase):
    """Request body model for creating a global station preset."""

    pass


class AccountStationPresetCreate(StationPresetBase):
    """Request body model for creating an account station preset."""

    pass


class GlobalStationPreset(StationPresetBase):
    """A global station preset."""

    id: Slug = Field(..., json_schema_extra={"example": "briceburg"})


class AccountStationPreset(StationPresetBase):
    """An account-specific station preset."""

    id: Slug = Field(..., json_schema_extra={"example": "briceburg-my-favorites"})
    account_id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
