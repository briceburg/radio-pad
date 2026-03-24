from __future__ import annotations

from pydantic import BaseModel, Field


class AuthenticatedIdentity(BaseModel):
    issuer: str
    subject: str
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


class GlobalAdmins(BaseModel):
    id: str = Field(default="global-admins")
    subjects: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)

    def allows(self, identity: AuthenticatedIdentity) -> bool:
        return identity.subject_key in self.subjects or identity.verified_email in {
            email.casefold() for email in self.emails
        }


class AccountAccess(BaseModel):
    id: str
    subjects: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)

    def allows(self, identity: AuthenticatedIdentity) -> bool:
        return identity.subject_key in self.subjects or identity.verified_email in {
            email.casefold() for email in self.emails
        }
