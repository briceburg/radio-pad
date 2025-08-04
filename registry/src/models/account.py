from pydantic import BaseModel, Field


class Account(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "briceburg"})
    name: str = Field(..., json_schema_extra={"example": "brice b"})
