from pydantic import BaseModel, Field, field_validator

from lib.types import Descriptor, Slug
from lib.validators import trim_name


class AccountBase(BaseModel):
    """Base model for accounts, containing common fields."""

    name: Descriptor = Field(..., json_schema_extra={"example": "brice b"})

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        return trim_name(v)


class AccountCreate(AccountBase):
    """Request body model for creating/updating an account via the PUT endpoint."""

    pass


class AccountSummary(BaseModel):
    """Abbreviated account model for list endpoints."""

    id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
    name: Descriptor = Field(..., json_schema_extra={"example": "brice b"})


class Account(AccountBase):
    """The full account model as stored and returned by the API."""

    id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
