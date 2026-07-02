import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, WebSocketException, status

from auth.socket_auth import validate_socket_client
from switchboard.broadcast import Broadcast

router = APIRouter()
logger = logging.getLogger("switchboard")
PLAYER_USER_AGENT_PREFIX = "RadioPad/"
AUTHENTICATION_REQUIRED_REASON = "Authentication required"
CONTROLLER_AUTH_TIMEOUT_SECONDS = 10
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


class _SessionExpired(Exception):
    pass


async def _authenticate_controller(websocket: WebSocket, account_id: str, player_id: str) -> tuple[bool, int | None]:
    try:
        async with asyncio.timeout(CONTROLLER_AUTH_TIMEOUT_SECONDS):
            payload = json.loads(await websocket.receive_text())
        if not isinstance(payload, dict):
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=AUTHENTICATION_REQUIRED_REASON)
        data = payload.get("data")
        if payload.get("event") != "authenticate" or not isinstance(data, dict) or "token" not in data:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=AUTHENTICATION_REQUIRED_REASON)
        token = data.get("token")
        if token is not None and not isinstance(token, str):
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason=AUTHENTICATION_REQUIRED_REASON)
        expires_at = await validate_socket_client(websocket, account_id, player_id, token or None)
    except WebSocketDisconnect:
        return False, None
    except (TimeoutError, json.JSONDecodeError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=AUTHENTICATION_REQUIRED_REASON)
        return False, None
    except WebSocketException as exc:
        await websocket.close(code=exc.code, reason=exc.reason)
        return False, None
    except Exception:
        logger.exception("Unexpected socket auth error for %s/%s", account_id, player_id)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Validation internal error")
        return False, None

    await websocket.send_json({"event": "authenticated", "data": {"expires_at": expires_at}})
    return True, expires_at


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


async def _run_loop(
    websocket: WebSocket,
    broadcast: Broadcast,
    player_key: str,
    is_player: bool,
    expires_at: int | None = None,
) -> None:
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
            try:
                if expires_at is None:
                    msg = await websocket.receive_text()
                else:
                    async with asyncio.timeout(max(expires_at - time.time(), 0)):
                        msg = await websocket.receive_text()
            except TimeoutError as exc:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=AUTHENTICATION_REQUIRED_REASON)
                raise _SessionExpired from exc
            try:
                payload = json.loads(msg)
                if not isinstance(payload, dict):
                    continue
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
    except* (_SessionExpired, WebSocketDisconnect):
        pass


@router.websocket("/{account_id}/{player_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    account_id: str,
    player_id: str,
) -> None:
    user_agent = websocket.headers.get("User-Agent", "")
    is_player = user_agent.startswith(PLAYER_USER_AGENT_PREFIX)
    player_key = f"{account_id}/{player_id}"
    radio_dial_url: str | None = None

    if is_player:
        radio_dial_url = websocket.headers.get("RadioPad-Radio-Dial-Url")
        if not radio_dial_url:
            await websocket.close(code=4000, reason="RadioPad-Radio-Dial-Url header required")
            return

    await websocket.accept()
    expires_at = None
    if not is_player:
        authenticated, expires_at = await _authenticate_controller(websocket, account_id, player_id)
        if not authenticated:
            return

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
        await _run_loop(websocket, broadcast, player_key, is_player=is_player, expires_at=expires_at)
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
                {"call_sign": None, "requested_call_sign": None, "failed_call_sign": None},
            )
