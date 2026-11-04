from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass

import httpx2
import jwt
from fastapi import HTTPException, status
from jwt import PyJWK, PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError, PyJWTError
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, ValidationError

from datastore.core import ExpiringCache
from lib.logging import logger


class RegistryIDToken(BaseModel):
    model_config = ConfigDict(extra="allow")

    iss: str
    sub: str
    aud: str | list[str]
    exp: int
    iat: int
    auth_time: int | None = None
    email: str | None = None
    email_verified: bool | None = None
    name: str | None = None


class _Discovery(BaseModel):
    issuer: str
    jwks_uri: AnyHttpUrl
    id_token_signing_alg_values_supported: list[str]


class _ProviderError(Exception):
    pass


class _SigningKeys(PyJWKClient):
    def get_signing_keys(self, refresh: bool = False) -> list[PyJWK]:
        # Provider failures must remain distinct from get_signing_key's unknown-kid error.
        # Keep key selection, synchronization, caching and rotation in PyJWT.
        try:
            return super().get_signing_keys(refresh)
        except (PyJWTError, ValueError) as error:
            raise _ProviderError("OIDC signing keys unavailable") from error


@dataclass(frozen=True)
class OIDCConfig:
    client_ids: tuple[str, ...]
    issuer: str
    base_authorization_server_uri: str
    signature_cache_ttl: int

    @classmethod
    def from_env(cls) -> OIDCConfig | None:
        client_ids_raw = os.environ.get("REGISTRY_AUTH_OIDC_CLIENT_IDS")
        issuer = os.environ.get("REGISTRY_AUTH_OIDC_ISSUER")

        if not client_ids_raw:
            return None
        if not issuer:
            raise ValueError("REGISTRY_AUTH_OIDC_ISSUER must be set when REGISTRY_AUTH_OIDC_CLIENT_IDS is configured")

        client_ids = tuple(dict.fromkeys(part.strip() for part in client_ids_raw.split(",") if part.strip()))
        if not client_ids:
            raise ValueError("REGISTRY_AUTH_OIDC_CLIENT_IDS must include at least one client id")

        base_uri = os.environ.get("REGISTRY_AUTH_OIDC_BASE_URI", issuer)
        cache_ttl = int(os.environ.get("REGISTRY_AUTH_OIDC_SIGNATURE_CACHE_TTL", "3600"))
        return cls(
            client_ids=client_ids,
            issuer=issuer,
            base_authorization_server_uri=base_uri,
            signature_cache_ttl=cache_ttl,
        )

    def build_auth_dependency(self) -> Callable[[str], RegistryIDToken]:
        discoveries: ExpiringCache[str, _SigningKeys] = ExpiringCache(
            ttl_seconds=self.signature_cache_ttl, max_entries=1
        )

        def discover() -> _SigningKeys:
            try:
                response = httpx2.get(
                    f"{self.base_authorization_server_uri.rstrip('/')}/.well-known/openid-configuration",
                    timeout=15,
                    follow_redirects=False,
                )
                response.raise_for_status()
                metadata = _Discovery.model_validate(response.json())
                if metadata.issuer != self.issuer or "RS256" not in metadata.id_token_signing_alg_values_supported:
                    raise ValueError("OIDC discovery does not match the configured issuer and signing algorithm")
                return _SigningKeys(
                    str(metadata.jwks_uri),
                    lifespan=self.signature_cache_ttl,
                    cache_jwk_set=self.signature_cache_ttl > 0,
                    timeout=15,
                )
            except (httpx2.HTTPError, ValueError, PyJWTError) as error:
                raise _ProviderError("OIDC discovery unavailable") from error

        def authenticate_user(raw_token: str) -> RegistryIDToken:
            try:
                header = jwt.get_unverified_header(raw_token)
                kid = header.get("kid")
                if header.get("alg") != "RS256" or not isinstance(kid, str) or not kid:
                    raise InvalidTokenError("Unsupported signing algorithm or missing key ID")
                keys = discoveries.get_or_load(self.issuer, discover)
                payload = jwt.decode(
                    raw_token,
                    keys.get_signing_key(kid),
                    algorithms=["RS256"],
                    audience=self.client_ids,
                    issuer=self.issuer,
                    options={"require": ["iss", "sub", "aud", "exp", "iat"]},
                )
                return RegistryIDToken.model_validate(payload)
            except (InvalidTokenError, PyJWKClientError, ValidationError) as error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid OIDC ID token",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from error
            except _ProviderError as error:
                logger.exception("OIDC provider verification failed")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="OIDC provider unavailable",
                ) from error

        return authenticate_user
