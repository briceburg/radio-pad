from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel, ConfigDict, ValidationError

from .models import AuthenticatedIdentity
from .oidc import RegistryIDToken

ACCESS_TOKEN_TTL_SECONDS = 60 * 60
SESSION_MAX_AGE_SECONDS = 30 * 24 * 60 * 60
SESSION_COOKIE_NAME = "radiopad-session"
_ALGORITHM = "HS256"


class SessionError(Exception):
    pass


class _AccessClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token_type: Literal["access"]
    oidc_issuer: str
    sub: str
    auth_time: int
    iat: int
    exp: int
    email: str | None = None
    email_verified: bool = False
    name: str | None = None

    def identity(self) -> AuthenticatedIdentity:
        return AuthenticatedIdentity(
            issuer=self.oidc_issuer,
            subject=self.sub,
            authenticated_at=self.auth_time,
            expires_at=self.exp,
            email=self.email,
            email_verified=self.email_verified,
            name=self.name,
        )


@dataclass(frozen=True)
class IssuedAccessToken:
    token: str
    expires_at: int
    identity: AuthenticatedIdentity


class AccessTokens:
    def __init__(
        self,
        secret: str,
        *,
        clock: Callable[[], float] = time.time,
        ttl_seconds: int = ACCESS_TOKEN_TTL_SECONDS,
    ) -> None:
        if len(secret.encode()) < 32:
            raise ValueError("REGISTRY_AUTH_SESSION_SECRET must contain at least 32 bytes")
        if ttl_seconds < 1:
            raise ValueError("access token lifetime must be positive")
        self._secret = secret
        self._clock = clock
        self._ttl_seconds = ttl_seconds

    @classmethod
    def from_env(cls) -> AccessTokens:
        secret = os.environ.get("REGISTRY_AUTH_SESSION_SECRET")
        if not secret:
            raise ValueError("REGISTRY_AUTH_SESSION_SECRET must be set when registry auth is enabled")
        return cls(secret)

    @staticmethod
    def identity_from_oidc(token: RegistryIDToken) -> AuthenticatedIdentity:
        if token.auth_time is not None and token.auth_time > token.iat:
            raise SessionError("Invalid OIDC authentication time")
        return AuthenticatedIdentity(
            issuer=token.iss,
            subject=token.sub,
            authenticated_at=token.auth_time if token.auth_time is not None else token.iat,
            expires_at=token.exp,
            email=token.email,
            email_verified=token.email_verified is True,
            name=token.name,
        )

    def issue(self, identity: AuthenticatedIdentity) -> IssuedAccessToken:
        now = int(self._clock())
        claims = _AccessClaims(
            token_type="access",
            oidc_issuer=identity.issuer,
            sub=identity.subject,
            auth_time=identity.authenticated_at,
            iat=now,
            exp=now + self._ttl_seconds,
            email=identity.email,
            email_verified=identity.email_verified,
            name=identity.name,
        )
        token = jwt.encode(claims.model_dump(mode="json"), self._secret, algorithm=_ALGORITHM)
        return IssuedAccessToken(token=token, expires_at=claims.exp, identity=claims.identity())

    def authenticate(self, token: str) -> AuthenticatedIdentity:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                options={
                    "require": ["exp", "iat", "sub"],
                    "verify_aud": False,
                    "verify_exp": False,
                },
            )
            claims = _AccessClaims.model_validate(payload)
        except (InvalidTokenError, ValidationError) as error:
            raise SessionError("Invalid access token") from error
        if claims.exp <= int(self._clock()):
            raise SessionError("Session expired")
        return claims.identity()
