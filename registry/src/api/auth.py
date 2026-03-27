from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status

from auth import AuthenticatedIdentity, AuthzStore, OIDCConfig, RegistryIDToken
from lib.logging import logger


@dataclass(frozen=True)
class AuthServices:
    authenticate_user: Callable[[str], RegistryIDToken] | None
    authz_store: AuthzStore | None

    @classmethod
    def from_env(cls) -> AuthServices:
        config = OIDCConfig.from_env()
        if config is None:
            logger.warning("Registry auth disabled: OIDC client_id/issuer not configured")
            return cls(authenticate_user=None, authz_store=None)
        logger.info(f"Registry auth enabled: issuer={config.issuer}")
        authz_store = AuthzStore()
        authz_store.seed()
        return cls(authenticate_user=config.build_auth_dependency(), authz_store=authz_store)

    @property
    def enabled(self) -> bool:
        return self.authenticate_user is not None and self.authz_store is not None


def get_auth_services(request: Request) -> AuthServices:
    services = getattr(request.app.state, "auth", None)
    if services is None or not isinstance(services, AuthServices):
        raise HTTPException(status_code=500, detail="Auth services not initialized")
    return cast(AuthServices, services)


def current_identity(
    request: Request,
    services: Annotated[AuthServices, Depends(get_auth_services)],
) -> AuthenticatedIdentity | None:
    if not services.enabled:
        return None

    auth_header = request.headers.get("Authorization")
    if auth_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required for write access",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, _, raw_token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not raw_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required for write access",
            headers={"WWW-Authenticate": "Bearer"},
        )

    assert services.authenticate_user is not None
    try:
        token = services.authenticate_user(raw_token.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return AuthenticatedIdentity(
        issuer=token.iss,
        subject=token.sub,
        email=token.email,
        email_verified=token.email_verified is True,
    )


def require_admin(
    identity: Annotated[AuthenticatedIdentity | None, Depends(current_identity)],
    services: Annotated[AuthServices, Depends(get_auth_services)],
) -> AuthenticatedIdentity | None:
    if not services.enabled:
        return None

    assert identity is not None
    assert services.authz_store is not None
    if services.authz_store.is_admin(identity):
        return identity

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


def require_account_manager(
    account_id: str,
    identity: Annotated[AuthenticatedIdentity | None, Depends(current_identity)],
    services: Annotated[AuthServices, Depends(get_auth_services)],
) -> AuthenticatedIdentity | None:
    if not services.enabled:
        return None

    assert identity is not None
    assert services.authz_store is not None
    if services.authz_store.can_manage_account(account_id, identity):
        return identity

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Account owner or admin access required",
    )
