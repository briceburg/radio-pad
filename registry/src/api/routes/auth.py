from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

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
    dependencies=[Depends(require_player_control_access)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def authorize_player_control() -> Response:
    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        headers={"Cache-Control": "no-store"},
    )
