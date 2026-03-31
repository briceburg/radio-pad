from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from auth import AuthenticatedIdentity, AuthzStore, OIDCConfig, RegistryIDToken
from lib.logging import logger

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthServices:
    authenticate_user: Callable[[str], RegistryIDToken] | None
    authz_store: AuthzStore | None

    @classmethod
    def from_env(cls) -> AuthServices:
        config = OIDCConfig.from_env()
        if config is None:
            logger.warning("Registry auth disabled: OIDC client_ids/issuer not configured")
            return cls(authenticate_user=None, authz_store=None)
        logger.info(f"Registry auth enabled: issuer={config.issuer}, client_ids={config.client_ids}")
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

    assert services.authenticate_user is not None
    try:
        token = services.authenticate_user(creds.credentials)
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
        # Treat missing email_verified as True, particularly for Google id_tokens which
        # may omit it when implicit (like via mobile Capacitor SDKs).
        # Only explicitly False means unverified.
        email_verified=token.email_verified is not False,
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

    logger.warning(f"403 Forbidden for {account_id}. Identity: {identity.model_dump()}")
    access = services.authz_store.get_account_access(account_id)
    if access:
        logger.warning(f"Account access allows emails: {access.emails}, subjects: {access.subjects}")
    else:
        logger.warning(f"No account access seeded for {account_id}")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Account owner or admin access required",
    )
