from pydantic import BaseModel, ConfigDict, Field, field_validator

from lib.types import Descriptor, Slug
from lib.validators import trim_name


class AccountSpec(BaseModel):
    """Writable account specification without its path-derived identity."""

    model_config = ConfigDict(extra="forbid")

    name: Descriptor = Field(..., json_schema_extra={"example": "brice b"})

    @field_validator("name", mode="before")
    @classmethod
    def _trim_name(cls, v: str) -> str:
        return trim_name(v)


class Account(AccountSpec):
    """The full account model as stored and returned by the API."""

    id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
