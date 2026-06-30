from pydantic import BaseModel


class AuthStatus(BaseModel):
    """Public registry authentication capability."""

    enabled: bool
