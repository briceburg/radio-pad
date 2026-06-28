from pydantic import BaseModel, ConfigDict, Field

from lib.types import Name, Slug


class AccountSpec(BaseModel):
    """Writable account specification without its path-derived identity."""

    model_config = ConfigDict(extra="forbid")

    name: Name = Field(..., json_schema_extra={"example": "brice b"})


class Account(AccountSpec):
    """The full account model as stored and returned by the API."""

    id: Slug = Field(..., json_schema_extra={"example": "briceburg"})
