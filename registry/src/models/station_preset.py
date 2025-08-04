from datetime import datetime

from pydantic import BaseModel, Field

from models.station import StationList


class StationPreset(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "briceburg"})
    lastUpdated: datetime = Field(
        ..., json_schema_extra={"example": datetime.now().isoformat()}
    )
    stations: StationList
