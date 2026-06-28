from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from lib.types import CallSign, StationKey


class StationSpec(BaseModel):
    """Writable Station specification without its account-qualified identity."""

    model_config = ConfigDict(extra="forbid")

    stream_url: HttpUrl = Field(..., json_schema_extra={"example": "https://www.wwoz.org/listen/hi"})


class Station(StationSpec):
    """Resolved station with its account-qualified key and call sign."""

    key: StationKey = Field(..., json_schema_extra={"example": "community/WWOZ"})
    call_sign: CallSign = Field(..., json_schema_extra={"example": "WWOZ"})
