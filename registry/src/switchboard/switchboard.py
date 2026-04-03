import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from auth.socket_auth import validate_socket_client
from switchboard.broadcast import Broadcast

router = APIRouter()
logger = logging.getLogger("switchboard")


@router.websocket("/{account_id}/{player_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    account_id: str,
    player_id: str,
    token: str | None = Query(default=None),
) -> None:
    user_agent = websocket.headers.get("User-Agent", "")
    is_player = user_agent.startswith("RadioPad/")
    is_authenticated_controller = not is_player
    player_key = f"{account_id}/{player_id}"
    stations_url: str | None = None

    # Authenticate controllers
    if not is_player:
        if not token:
            await websocket.close(code=4001, reason="Authentication token required")
            return
        try:
            await validate_socket_client(websocket, account_id, player_id, token)
        except Exception as e:
            logger.warning(f"Socket auth failed for {player_key}: {e}")
            await websocket.close(code=4003, reason="Unauthorized")
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
        await broadcast.publish(player_key, json.dumps({"event": "stations_url", "data": stations_url}))

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

                    if event == "station_playing":
                        if is_player:
                            await broadcast.publish(player_key, json.dumps({"event": "station_playing", "data": data}))
                    elif event == "station_request":
                        if is_authenticated_controller:
                            await broadcast.publish(player_key, json.dumps({"event": "station_request", "data": data}))
                    elif event == "ping":
                        await websocket.send_json({"event": "pong"})
                except json.JSONDecodeError:
                    continue
        except WebSocketDisconnect:
            pass

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(sender())
            tg.create_task(receiver())
    except* WebSocketDisconnect:
        pass
    finally:
        if is_player:
            await broadcast.publish(player_key, json.dumps({"event": "station_playing", "data": None}))
