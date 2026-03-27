from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from fastapi_oidc.auth import get_auth
from fastapi_oidc.types import IDToken


class RegistryIDToken(IDToken):
    email: str | None = None
    email_verified: bool | None = None


@dataclass(frozen=True)
class OIDCConfig:
    client_id: str
    issuer: str
    base_authorization_server_uri: str
    audience: str
    signature_cache_ttl: int

    @classmethod
    def from_env(cls) -> OIDCConfig | None:
        client_id = os.environ.get("REGISTRY_AUTH_OIDC_CLIENT_ID")
        issuer = os.environ.get("REGISTRY_AUTH_OIDC_ISSUER")

        if not client_id and not issuer:
            return None
        if not client_id or not issuer:
            raise ValueError("REGISTRY_AUTH_OIDC_CLIENT_ID and REGISTRY_AUTH_OIDC_ISSUER must both be set")

        base_uri = os.environ.get("REGISTRY_AUTH_OIDC_BASE_URI", issuer)
        audience = os.environ.get("REGISTRY_AUTH_OIDC_AUDIENCE") or client_id
        cache_ttl = int(os.environ.get("REGISTRY_AUTH_OIDC_SIGNATURE_CACHE_TTL", "3600"))
        return cls(
            client_id=client_id,
            issuer=issuer,
            base_authorization_server_uri=base_uri,
            audience=audience,
            signature_cache_ttl=cache_ttl,
        )

    def build_auth_dependency(self) -> Callable[[str], RegistryIDToken]:
        return cast(
            Callable[[str], RegistryIDToken],
            get_auth(
                client_id=self.client_id,
                audience=self.audience,
                base_authorization_server_uri=self.base_authorization_server_uri,
                issuer=self.issuer,
                signature_cache_ttl=self.signature_cache_ttl,
                token_type=RegistryIDToken,
            ),
        )
