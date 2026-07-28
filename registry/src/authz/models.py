from __future__ import annotations

from datetime import UTC, datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from auth import AuthenticatedIdentity
from lib.types import Slug


def _normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if not normalized or normalized.count("@") != 1 or any(character.isspace() for character in normalized):
        raise ValueError("invalid email address")
    return normalized


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
        return sorted({_normalize_email(email) for email in emails})

    @model_validator(mode="after")
    def require_owner(self) -> Self:
        if not self.subjects and not self.emails:
            raise ValueError("an account authz document must contain at least one owner")
        return self

    def allows(self, identity: AuthenticatedIdentity) -> bool:
        return identity.subject_key in self.subjects or identity.verified_email in self.emails


class SessionRevocations(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default="session-revocations", pattern=r"^session-revocations$")
    revoked_before: AwareDatetime | None = None
    subjects: dict[str, AwareDatetime] = Field(default_factory=dict)
    emails: dict[str, AwareDatetime] = Field(default_factory=dict)

    @field_validator("subjects")
    @classmethod
    def validate_subjects(cls, subjects: dict[str, AwareDatetime]) -> dict[str, AwareDatetime]:
        normalized = {subject.strip(): cutoff for subject, cutoff in subjects.items()}
        if any(not subject for subject in normalized):
            raise ValueError("subjects cannot contain empty keys")
        return dict(sorted(normalized.items()))

    @field_validator("emails")
    @classmethod
    def normalize_emails(cls, emails: dict[str, AwareDatetime]) -> dict[str, AwareDatetime]:
        normalized = {_normalize_email(email): cutoff for email, cutoff in emails.items()}
        return dict(sorted(normalized.items()))

    def allows(self, identity: AuthenticatedIdentity) -> bool:
        authenticated_at = datetime.fromtimestamp(identity.authenticated_at, tz=UTC)
        cutoffs = (
            self.revoked_before,
            self.subjects.get(identity.subject_key),
            self.emails.get(identity.verified_email or ""),
        )
        return all(cutoff is None or authenticated_at > cutoff for cutoff in cutoffs)
