from __future__ import annotations

from pydantic import BaseModel


class AuthenticatedIdentity(BaseModel):
    issuer: str
    subject: str
    expires_at: int | None = None
    email: str | None = None
    email_verified: bool = False

    @property
    def subject_key(self) -> str:
        return f"oidc:{self.issuer}:{self.subject}"

    @property
    def verified_email(self) -> str | None:
        if self.email and self.email_verified:
            return self.email.casefold()
        return None
