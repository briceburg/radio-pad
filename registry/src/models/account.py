from pydantic import BaseModel, Field


class AccountBase(BaseModel):
    """Base model for accounts, containing common fields."""

    name: str = Field(..., json_schema_extra={"example": "brice b"})


class AccountCreate(AccountBase):
    """Request body model for creating/updating an account via the PUT endpoint."""


class Account(AccountBase):
    """The full account model as stored and returned by the API."""

    id: str = Field(..., json_schema_extra={"example": "briceburg"})
