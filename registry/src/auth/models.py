from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from lib.types import Slug


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


class AccountOwners(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: Slug
    subjects: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)

    @field_validator("subjects")
    @classmethod
    def normalize_subjects(cls, subjects: list[str]) -> list[str]:
        normalized = [subject.strip() for subject in subjects]
        if any(not subject for subject in normalized):
            raise ValueError("subjects cannot contain empty values")
        return sorted(set(normalized))

    @field_validator("emails")
    @classmethod
    def normalize_emails(cls, emails: list[str]) -> list[str]:
        normalized = [email.strip().casefold() for email in emails]
        if any(
            not email or email.count("@") != 1 or any(character.isspace() for character in email)
            for email in normalized
        ):
            raise ValueError("emails must contain valid email addresses")
        return sorted(set(normalized))

    @model_validator(mode="after")
    def require_owner(self) -> Self:
        if not self.subjects and not self.emails:
            raise ValueError("an account authorization document must contain at least one owner")
        return self

    def allows(self, identity: AuthenticatedIdentity) -> bool:
        return identity.subject_key in self.subjects or identity.verified_email in self.emails
