from pydantic import BaseModel, Field, field_validator

from lib.types import Slug


class AccountBase(BaseModel):
    """Base model for accounts, containing common fields."""

    name: str = Field(..., json_schema_extra={"example": "brice b"})

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        s = str(v).strip()
        if not s:
            raise ValueError("name cannot be empty")
        return s


class AccountCreate(AccountBase):
    """Request body model for creating/updating an account via the PUT endpoint."""

    pass


class Account(AccountBase):
    """The full account model as stored and returned by the API."""

    id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
