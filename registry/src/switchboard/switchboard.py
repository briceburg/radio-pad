import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, WebSocketException

from auth.socket_auth import validate_socket_client
from switchboard.broadcast import Broadcast

router = APIRouter()
logger = logging.getLogger("switchboard")
PLAYER_USER_AGENT_PREFIX = "RadioPad/"


def controller_auth_required(websocket: WebSocket) -> bool:
    services = getattr(websocket.app.state, "auth", None)
    if services is not None:
        return bool(getattr(services, "enabled", False))

    return False


async def publish_event(broadcast: Broadcast, channel: str, event: str, data: object) -> None:
    message = json.dumps({"event": event, "data": data})
    broadcast.set_state(channel, message)
    await broadcast.publish(channel, message)


async def _run_loop(websocket: WebSocket, broadcast: Broadcast, player_key: str, is_player: bool) -> None:
    async def sender() -> None:
        async with broadcast.subscribe(player_key, replay=not is_player) as subscriber:
            async for event in subscriber:
                try:
                    await websocket.send_text(event.message)
                except Exception:
                    logger.debug("Send failed for %s: %s", player_key, event.message[:80])
                    break

    async def receiver() -> None:
        while True:
            msg = await websocket.receive_text()
            try:
                payload = json.loads(msg)
                event = payload.get("event")
                data = payload.get("data")
                if not event:
                    continue

                match event:
                    case "station_playing" if is_player:
                        await publish_event(broadcast, player_key, "station_playing", data)
                    case "station_request" if not is_player:
                        await publish_event(broadcast, player_key, "station_request", data)
                    case "ping":
                        await websocket.send_json({"event": "pong"})
            except json.JSONDecodeError:
                continue

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(sender())
            tg.create_task(receiver())
    except* WebSocketDisconnect:
        pass


@router.websocket("/{account_id}/{player_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    account_id: str,
    player_id: str,
    token: str | None = Query(default=None),
) -> None:
    user_agent = websocket.headers.get("User-Agent", "")
    is_player = user_agent.startswith(PLAYER_USER_AGENT_PREFIX)
    player_key = f"{account_id}/{player_id}"
    stations_url: str | None = None

    # Authenticate controllers
    if not is_player:
        if controller_auth_required(websocket) and not token:
            await websocket.close(code=4001, reason="Authentication token required")
            return
        try:
            await validate_socket_client(websocket, account_id, player_id, token)
        except WebSocketException as e:
            logger.warning("Socket auth failed for %s: %s", player_key, e)
            await websocket.close(code=e.code, reason=e.reason)
            return
        except Exception:
            logger.exception("Unexpected socket auth error for %s", player_key)
            await websocket.close(code=1011, reason="Validation internal error")
            return
    else:
        stations_url = websocket.headers.get("RadioPad-Stations-Url")
        if not stations_url:
            await websocket.close(code=4000, reason="RadioPad-Stations-Url header required")
            return

    await websocket.accept()

    broadcast: Broadcast | None = getattr(websocket.app.state, "broadcast", None)
    if not broadcast:
        logger.error("Broadcast not configured on app state")
        await websocket.close()
        return

    if is_player:
        await publish_event(broadcast, player_key, "stations_url", stations_url)

    try:
        await _run_loop(websocket, broadcast, player_key, is_player=is_player)
    finally:
        if is_player:
            broadcast.clear_state(player_key)
            await publish_event(broadcast, player_key, "station_playing", None)
