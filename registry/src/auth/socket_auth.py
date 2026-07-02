import httpx2
from fastapi import HTTPException, Request, WebSocket, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import AuthServices, current_identity, require_player_control_access
from api.exceptions import NotFoundError
from datastore import DataStore
from lib.constants import PROFILES, REGISTRY_URL

_ACCESS_DENIED_HTTP_STATUSES = (401, 403, 404)


def _denial_reason(status_code: int) -> str:
    return "Authentication required" if status_code == status.HTTP_401_UNAUTHORIZED else "Access denied"


async def validate_socket_client(
    request: Request | WebSocket, account_id: str, player_id: str, token: str | None
) -> int | None:
    profiles = getattr(request.app.state, "profiles", PROFILES)
    if "api" in profiles:
        return await validate_local(request, account_id, player_id, token)
    return await validate_remote(request, account_id, player_id, token)


async def validate_local(
    request: Request | WebSocket, account_id: str, player_id: str, token: str | None
) -> int | None:
    services = getattr(request.app.state, "auth", None)
    ds = getattr(request.app.state, "store", None)
    if not isinstance(services, AuthServices) or not isinstance(ds, DataStore):
        raise RuntimeError("Local socket validation is not initialized")

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token) if token else None

    try:
        identity = current_identity(services, creds)
        identity = require_player_control_access(account_id, player_id, ds, identity, services)
    except (HTTPException, NotFoundError) as exc:
        if isinstance(exc, NotFoundError) or exc.status_code in _ACCESS_DENIED_HTTP_STATUSES:
            status_code = status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else exc.status_code
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason=_denial_reason(status_code),
            ) from exc
        raise
    return identity.expires_at if identity else None


async def validate_remote(
    request: Request | WebSocket, account_id: str, player_id: str, token: str | None
) -> int | None:
    url = f"{REGISTRY_URL.rstrip('/')}/auth/players/{account_id}/{player_id}/control"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    client: httpx2.AsyncClient = request.app.state.http_client
    resp = await client.get(url, headers=headers)

    if resp.status_code in _ACCESS_DENIED_HTTP_STATUSES:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=_denial_reason(resp.status_code))
    if resp.status_code != 204:
        raise RuntimeError(f"Remote socket validation returned HTTP {resp.status_code}")
    expires_at = resp.headers.get("RadioPad-Token-Expires-At")
    return int(expires_at) if expires_at else None
