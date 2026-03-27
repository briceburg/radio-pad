from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from fastapi import HTTPException, status
from fastapi_oidc.auth import get_auth
from fastapi_oidc.types import IDToken


class RegistryIDToken(IDToken):
    email: str | None = None
    email_verified: bool | None = None


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

        if not client_ids_raw and not issuer:
            return None
        if not client_ids_raw or not issuer:
            raise ValueError("REGISTRY_AUTH_OIDC_CLIENT_IDS and REGISTRY_AUTH_OIDC_ISSUER must both be set")

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
        verifiers = [
            cast(
                Callable[[str], RegistryIDToken],
                get_auth(
                    client_id=client_id,
                    audience=client_id,
                    base_authorization_server_uri=self.base_authorization_server_uri,
                    issuer=self.issuer,
                    signature_cache_ttl=self.signature_cache_ttl,
                    token_type=RegistryIDToken,
                ),
            )
            for client_id in self.client_ids
        ]

        def authenticate_user(raw_token: str) -> RegistryIDToken:
            last_error: HTTPException | None = None
            for verifier in verifiers:
                try:
                    return verifier(raw_token)
                except HTTPException as exc:
                    if exc.status_code != status.HTTP_401_UNAUTHORIZED:
                        raise
                    last_error = exc

            raise last_error or HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )

        return authenticate_user
