from pydantic import BaseModel, Field


class AccountCreate(BaseModel):
    """Request body model for creating/updating an account via the PUT endpoint."""

    name: str = Field(..., json_schema_extra={"example": "brice b"})


class Account(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "briceburg"})
    name: str = Field(..., json_schema_extra={"example": "brice b"})
