from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, ValidationError

from auth import AuthenticatedIdentity, IssuedAccessToken, SessionError

from ..auth import AuthServices, bearer_scheme, get_auth_services, require_player_control_access

router = APIRouter(prefix="/auth")


class SessionIdentity(BaseModel):
    subject: str
    email: str | None
    name: str | None


class SessionResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: int
    identity: SessionIdentity


def _session_response(access: IssuedAccessToken) -> SessionResponse:
    return SessionResponse(
        access_token=access.token,
        expires_at=access.expires_at,
        identity=SessionIdentity(
            subject=access.identity.subject,
            email=access.identity.verified_email,
            name=access.identity.name,
        ),
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/status")
async def get_auth_status(
    response: Response,
    services: Annotated[AuthServices, Depends(get_auth_services)],
) -> dict[str, bool]:
    _no_store(response)
    return {"enabled": services.enabled}


@router.post("/session", response_model=SessionResponse)
def create_session(
    request: Request,
    response: Response,
    services: Annotated[AuthServices, Depends(get_auth_services)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> SessionResponse:
    if not services.enabled:
        raise _unauthorized("Registry auth is disabled")
    if not creds:
        raise _unauthorized("OIDC ID token required")

    try:
        identity = services.authenticate_oidc_token(creds.credentials)
    except SessionError as error:
        raise _unauthorized(str(error)) from error

    request.session.clear()
    request.session.update(identity.model_dump(mode="json", exclude={"expires_at"}))
    assert services.access_tokens is not None
    access = services.access_tokens.issue(identity)
    _no_store(response)
    return _session_response(access)


@router.post("/session/refresh", response_model=SessionResponse)
def refresh_session(
    request: Request,
    response: Response,
    services: Annotated[AuthServices, Depends(get_auth_services)],
    session_action: Annotated[str | None, Header(alias="RadioPad-Session")] = None,
) -> SessionResponse:
    if not services.enabled:
        raise _unauthorized("Registry auth is disabled")
    if session_action != "refresh":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Session refresh header required")
    try:
        identity = AuthenticatedIdentity.model_validate(request.session)
    except ValidationError as error:
        raise _unauthorized("Session expired—sign in again") from error
    try:
        services.require_active_session(identity)
    except SessionError as error:
        raise _unauthorized(str(error)) from error

    request.session.update()
    assert services.access_tokens is not None
    access = services.access_tokens.issue(identity)
    _no_store(response)
    return _session_response(access)


@router.delete("/session", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(request: Request, response: Response) -> Response:
    request.session.clear()
    _no_store(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get(
    "/players/{account_id}/{player_id}/control",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def authorize_player_control(
    identity: Annotated[AuthenticatedIdentity | None, Depends(require_player_control_access)],
) -> Response:
    headers = {"Cache-Control": "no-store"}
    if identity and identity.expires_at is not None:
        headers["RadioPad-Token-Expires-At"] = str(identity.expires_at)
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers=headers,
    )
