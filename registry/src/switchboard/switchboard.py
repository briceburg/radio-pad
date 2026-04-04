import asyncio
import json
import logging
from collections.abc import Coroutine
from contextlib import suppress

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, WebSocketException

from auth.socket_auth import validate_socket_client
from switchboard.broadcast import Broadcast

router = APIRouter()
logger = logging.getLogger("switchboard")
PLAYER_USER_AGENT_PREFIX = "RadioPad/"


async def publish_event(broadcast: Broadcast, channel: str, event: str, data: object) -> None:
    await broadcast.publish(channel, json.dumps({"event": event, "data": data}))


async def run_session_tasks(*coroutines: Coroutine[object, object, None]) -> None:
    tasks: list[asyncio.Task[None]] = [asyncio.create_task(coro) for coro in coroutines]
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in pending:
            with suppress(asyncio.CancelledError):
                await task
        for task in done:
            exc = task.exception()
            if exc is not None:
                raise exc
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()


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
        if not token:
            await websocket.close(code=4001, reason="Authentication token required")
            return
        try:
            await validate_socket_client(websocket, account_id, player_id, token)
        except WebSocketException as e:
            logger.warning(f"Socket auth failed for {player_key}: {e}")
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

    async def sender() -> None:
        async with broadcast.subscribe(player_key) as subscriber:
            async for event in subscriber:
                try:
                    await websocket.send_text(event.message)
                except Exception:
                    logger.debug("Send failed for %s: %s", player_key, event.message[:80])
                    break

    async def receiver() -> None:
        try:
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
        except WebSocketDisconnect:
            pass

    try:
        await run_session_tasks(sender(), receiver())
    except* WebSocketDisconnect:
        pass
    finally:
        if is_player:
            await publish_event(broadcast, player_key, "station_playing", None)
