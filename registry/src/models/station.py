from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from lib.types import CallSign, Descriptor, StationKey
from lib.validators import trim_name


class StationSpec(BaseModel):
    """Writable Station specification without its account-qualified identity."""

    model_config = ConfigDict(extra="forbid")

    display_name: Descriptor | None = Field(default=None, json_schema_extra={"example": "WWOZ 90.7 FM"})
    stream_url: HttpUrl = Field(..., json_schema_extra={"example": "https://www.wwoz.org/listen/hi"})

    @field_validator("display_name", mode="before")
    @classmethod
    def _trim_display_name(cls, value: object) -> object:
        return trim_name(value) if value is not None else None


class Station(StationSpec):
    """Resolved station with its account-qualified key and call sign."""

    key: StationKey = Field(..., json_schema_extra={"example": "community/WWOZ"})
    call_sign: CallSign = Field(..., json_schema_extra={"example": "WWOZ"})
