import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, WebSocketException, status

from auth.socket_auth import validate_socket_client
from switchboard.broadcast import Broadcast

router = APIRouter()
logger = logging.getLogger("switchboard")
PLAYER_USER_AGENT_PREFIX = "RadioPad/"
RETAINED_EVENTS = {"radio_dial_url", "player_presence", "playback_state"}
PLAYER_STATUS_SCOPES = {"radio_dial", "switchboard", "playback"}
PLAYER_COMMAND_EVENTS = {
    "playback_start",
    "playback_stop",
    "volume_up",
    "volume_down",
}
PLAYER_STATE_EVENTS = {
    "playback_state",
    "player_status",
}
ACTIVE_PLAYER_CONNECTIONS: set[str] = set()


def _state_key(event: str, data: object) -> str | None:
    if event in RETAINED_EVENTS:
        return event

    if event == "player_status" and isinstance(data, dict):
        scope = data.get("scope")
        level = data.get("level")
        if scope in PLAYER_STATUS_SCOPES and level != "ok":
            return f"player_status:{scope}"

    return None


def _cleared_state_key(event: str, data: object) -> str | None:
    if event == "player_status" and isinstance(data, dict):
        scope = data.get("scope")
        level = data.get("level")
        if scope in PLAYER_STATUS_SCOPES and level == "ok":
            return f"player_status:{scope}"

    return None


async def publish_event(broadcast: Broadcast, channel: str, event: str, data: object) -> None:
    message = json.dumps({"event": event, "data": data})
    key_to_clear = _cleared_state_key(event, data)
    if key_to_clear:
        broadcast.clear_state_key(channel, key_to_clear)

    key_to_retain = _state_key(event, data)
    if key_to_retain:
        broadcast.set_state(channel, key_to_retain, message)
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
                    case player_event if is_player and player_event in PLAYER_STATE_EVENTS:
                        await publish_event(broadcast, player_key, player_event, data)
                    case command_event if not is_player and command_event in PLAYER_COMMAND_EVENTS:
                        await publish_event(broadcast, player_key, command_event, data)
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
    radio_dial_url: str | None = None

    # Authenticate controllers
    if not is_player:
        try:
            await validate_socket_client(websocket, account_id, player_id, token)
        except WebSocketException:
            raise
        except Exception as exc:
            logger.exception("Unexpected socket auth error for %s", player_key)
            raise WebSocketException(code=status.WS_1011_INTERNAL_ERROR, reason="Validation internal error") from exc
    else:
        radio_dial_url = websocket.headers.get("RadioPad-Radio-Dial-Url")
        if not radio_dial_url:
            await websocket.close(code=4000, reason="RadioPad-Radio-Dial-Url header required")
            return

    await websocket.accept()

    broadcast: Broadcast | None = getattr(websocket.app.state, "broadcast", None)
    if not broadcast:
        logger.error("Broadcast not configured on app state")
        await websocket.close()
        return

    if is_player:
        if player_key in ACTIVE_PLAYER_CONNECTIONS:
            await websocket.close(code=4002, reason="Player already connected")
            return
        ACTIVE_PLAYER_CONNECTIONS.add(player_key)

    try:
        if is_player:
            await publish_event(
                broadcast,
                player_key,
                "player_presence",
                {"connected": True},
            )
            await publish_event(
                broadcast,
                player_key,
                "radio_dial_url",
                radio_dial_url,
            )
        await _run_loop(websocket, broadcast, player_key, is_player=is_player)
    finally:
        if is_player:
            ACTIVE_PLAYER_CONNECTIONS.discard(player_key)
            broadcast.clear_state(player_key)
            await publish_event(
                broadcast,
                player_key,
                "player_presence",
                {"connected": False},
            )
            await publish_event(
                broadcast,
                player_key,
                "playback_state",
                {"call_sign": None},
            )
