import httpx2
from fastapi import HTTPException, Request, WebSocket, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import AuthServices, current_identity, require_player_control_access
from api.exceptions import NotFoundError
from datastore import DataStore
from lib.constants import PROFILES, REGISTRY_URL

_ACCESS_DENIED_HTTP_STATUSES = (401, 403, 404)


async def validate_socket_client(
    request: Request | WebSocket, account_id: str, player_id: str, token: str | None
) -> None:
    profiles = getattr(request.app.state, "profiles", PROFILES)
    if "api" in profiles:
        await validate_local(request, account_id, player_id, token)
    else:
        await validate_remote(request, account_id, player_id, token)


async def validate_local(request: Request | WebSocket, account_id: str, player_id: str, token: str | None) -> None:
    services = getattr(request.app.state, "auth", None)
    ds = getattr(request.app.state, "store", None)
    if not isinstance(services, AuthServices) or not isinstance(ds, DataStore):
        raise RuntimeError("Local socket validation is not initialized")

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token) if token else None

    try:
        identity = current_identity(services, creds)
        require_player_control_access(account_id, player_id, ds, identity, services)
    except (HTTPException, NotFoundError) as exc:
        if isinstance(exc, NotFoundError) or exc.status_code in _ACCESS_DENIED_HTTP_STATUSES:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized access") from exc
        raise


async def validate_remote(request: Request | WebSocket, account_id: str, player_id: str, token: str | None) -> None:
    url = f"{REGISTRY_URL.rstrip('/')}/auth/players/{account_id}/{player_id}/control"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    client: httpx2.AsyncClient = request.app.state.http_client
    resp = await client.get(url, headers=headers)

    if resp.status_code in _ACCESS_DENIED_HTTP_STATUSES:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized access")
    if resp.status_code != 204:
        raise RuntimeError(f"Remote socket validation returned HTTP {resp.status_code}")
