from typing import List

from pydantic import BaseModel, Field, HttpUrl


class Station(BaseModel):
    name: str = Field(..., json_schema_extra={"example": "WWOZ"})
    url: HttpUrl = Field(
        ..., json_schema_extra={"example": "https://www.wwoz.org/listen/hi"}
    )
    color: str = Field(
        default="#000077",
        pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
    )


class StationList(BaseModel):
    stations: List[Station]
