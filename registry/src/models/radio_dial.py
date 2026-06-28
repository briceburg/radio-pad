from pydantic import BaseModel, ConfigDict, Field, model_validator

from lib.keys import split_key
from lib.types import Name, RadioDialKey, StationKey

from .station import Station


class _RadioDialMetadata(BaseModel):
    name: Name = Field(..., json_schema_extra={"example": "Casa Briceburg"})
    description: str | None = Field(default=None, json_schema_extra={"example": "A community-curated radio dial."})
    discoverable: bool = Field(
        default=False,
        description="Whether clients should surface this RadioDial in discovery; this is not access control",
    )


class RadioDialSpec(_RadioDialMetadata):
    """Writable RadioDial specification containing ordered Station keys."""

    model_config = ConfigDict(extra="forbid")

    stations: list[StationKey]

    @model_validator(mode="after")
    def _ensure_unique_call_signs(self) -> "RadioDialSpec":
        seen: set[str] = set()
        for station_key in self.stations:
            _, call_sign = split_key(station_key)
            if call_sign in seen:
                raise ValueError(f"Duplicate station call sign: {call_sign}")
            seen.add(call_sign)
        return self


class RadioDialSummary(_RadioDialMetadata):
    """Reduced RadioDial representation returned by list and discovery calls."""

    key: RadioDialKey = Field(..., json_schema_extra={"example": "community/briceburg"})


class RadioDial(RadioDialSummary):
    """Complete RadioDial resource with current Stations."""

    stations: list[Station]
