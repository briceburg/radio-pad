from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import AccessTokens, AuthenticatedIdentity, OIDCConfig, RegistryIDToken, SessionError
from authz import AuthzStore
from lib.logging import logger

from .helpers import get_or_404
from .types import DS

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthServices:
    authenticate_oidc: Callable[[str], RegistryIDToken] | None
    authz_store: AuthzStore | None
    access_tokens: AccessTokens | None

    @classmethod
    def from_env(cls) -> AuthServices:
        config = OIDCConfig.from_env()
        if config is None:
            logger.warning("Registry auth disabled: OIDC client_ids/issuer not configured")
            return cls(authenticate_oidc=None, authz_store=None, access_tokens=None)
        logger.info("Registry auth enabled: issuer=%s, client_id_count=%s", config.issuer, len(config.client_ids))
        access_tokens = AccessTokens.from_env()
        authz_store = AuthzStore()
        authz_store.seed()
        authz_store.check_backend_access()
        return cls(
            authenticate_oidc=config.build_auth_dependency(),
            authz_store=authz_store,
            access_tokens=access_tokens,
        )

    @property
    def enabled(self) -> bool:
        return self.authenticate_oidc is not None and self.authz_store is not None and self.access_tokens is not None

    def authenticate_oidc_token(self, raw_token: str) -> AuthenticatedIdentity:
        if not self.enabled:
            raise ValueError("Registry auth is disabled")
        assert self.authenticate_oidc is not None
        assert self.access_tokens is not None
        token = self.authenticate_oidc(raw_token)
        identity = self.access_tokens.identity_from_oidc(token)
        self.require_active_session(identity)
        return identity

    def authenticate_access_token(self, raw_token: str) -> AuthenticatedIdentity:
        if not self.enabled:
            raise ValueError("Registry auth is disabled")
        assert self.access_tokens is not None
        identity = self.access_tokens.authenticate(raw_token)
        self.require_active_session(identity)
        return identity

    def require_active_session(self, identity: AuthenticatedIdentity) -> None:
        assert self.authz_store is not None
        if not self.authz_store.is_session_allowed(identity):
            raise SessionError("Session revoked—sign in again")


def get_auth_services(request: Request) -> AuthServices:
    services = getattr(request.app.state, "auth", None)
    if services is None or not isinstance(services, AuthServices):
        raise HTTPException(status_code=500, detail="Auth services not initialized")
    return services


def current_identity(
    services: Annotated[AuthServices, Depends(get_auth_services)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> AuthenticatedIdentity | None:
    if not services.enabled:
        return None

    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return services.authenticate_access_token(creds.credentials)
    except SessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_account_owner(
    account_id: str,
    identity: Annotated[AuthenticatedIdentity | None, Depends(current_identity)],
    services: Annotated[AuthServices, Depends(get_auth_services)],
) -> AuthenticatedIdentity | None:
    if not services.enabled:
        return None

    assert identity is not None
    assert services.authz_store is not None
    if services.authz_store.is_account_owner(account_id, identity):
        return identity

    logger.warning("Account-owner access denied for %s", account_id)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Account owner access required",
    )


def require_player_control_access(
    account_id: str,
    player_id: str,
    ds: DS,
    identity: Annotated[AuthenticatedIdentity | None, Depends(current_identity)],
    services: Annotated[AuthServices, Depends(get_auth_services)],
) -> AuthenticatedIdentity | None:
    identity = require_account_owner(account_id, identity, services)
    get_or_404(
        ds.players.get(player_id, path_params={"account_id": account_id}),
        "Player not found",
        account_id=account_id,
        player_id=player_id,
    )
    return identity
