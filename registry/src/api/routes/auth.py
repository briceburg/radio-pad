from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from auth import AuthenticatedIdentity

from ..auth import AuthServices, get_auth_services, require_player_control_access

router = APIRouter(prefix="/auth")


@router.get("/status")
async def get_auth_status(
    response: Response,
    services: Annotated[AuthServices, Depends(get_auth_services)],
) -> dict[str, bool]:
    response.headers["Cache-Control"] = "no-store"
    return {"enabled": services.enabled}


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
