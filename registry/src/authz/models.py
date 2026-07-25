from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from auth import AuthenticatedIdentity
from lib.types import Slug


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
            raise ValueError("an account authz document must contain at least one owner")
        return self

    def allows(self, identity: AuthenticatedIdentity) -> bool:
        return identity.subject_key in self.subjects or identity.verified_email in self.emails
