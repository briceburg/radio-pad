import httpx
from fastapi import Request, WebSocket, WebSocketException, status
from fastapi.security import HTTPAuthorizationCredentials

from api.auth import current_identity, require_account_manager
from lib.constants import PROFILES, REGISTRY_URL
from lib.logging import logger


async def validate_socket_client(
    request: Request | WebSocket, account_id: str, player_id: str, token: str | None
) -> None:
    if "api" in PROFILES:
        await validate_local(request, account_id, player_id, token)
    else:
        await validate_remote(request, account_id, player_id, token)


async def validate_local(request: Request | WebSocket, account_id: str, player_id: str, token: str | None) -> None:
    services = getattr(request.app.state, "auth", None)
    if services is None or not services.enabled:
        return

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token) if token else None

    try:
        identity = current_identity(services, creds)
        require_account_manager(account_id, identity, services)
    except Exception as e:
        logger.warning(f"Local socket validation failed for {account_id}/{player_id}: {e!s}")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized access") from e


async def validate_remote(request: Request | WebSocket, account_id: str, player_id: str, token: str | None) -> None:
    url = f"{REGISTRY_URL.rstrip('/')}/accounts/{account_id}/players/{player_id}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    client: httpx.AsyncClient = request.app.state.http_client

    try:
        resp = await client.get(url, headers=headers)
    except httpx.HTTPError as e:
        logger.error(f"Remote socket validation failed: {e}")
        raise WebSocketException(code=status.WS_1011_INTERNAL_ERROR, reason="Validation internal error") from e

    if resp.status_code != 200:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized access via remote")
