#!/usr/bin/env python

import asyncio
import json
import logging
import os
import signal

import websockets
from http import HTTPStatus
from websockets.asyncio.server import broadcast, serve

CURRENT_STATION = None


def mkmsg(event: str, data) -> str:
    return json.dumps({"event": event, "data": data})


async def switchboard(websocket):
    global CURRENT_STATION

    def broadcast_all(event: str, data):
        broadcast(websocket.server.connections, mkmsg(event, data))

    try:
        broadcast_all("client_count", len(websocket.server.connections))
        await websocket.send(mkmsg("station_playing", CURRENT_STATION))

        async for msg in websocket:
            try:
                event, data = (lambda m: (m.get("event"), m.get("data")))(
                    json.loads(msg)
                )

                if not event:
                    return await websocket.close(
                        code=1007,
                        reason='Invalid message format. Missing "event" field.',
                    )
            except json.JSONDecodeError:
                return await websocket.close(
                    code=1007,
                    reason='Invalid message format. Expected JSON with "event" and "data" fields.',
                )

            if event == "station_playing":
                CURRENT_STATION = data
                broadcast_all("station_playing", CURRENT_STATION)
            elif event == "station_request":
                broadcast_all("station_request", data)
            else:
                return await websocket.close(
                    code=1007,
                    reason=f"Unknown event in message: {event}",
                )
    except websockets.exceptions.ConnectionClosedError:
        # Suppress expected disconnect errors
        pass
    finally:
        broadcast_all("client_count", len(websocket.server.connections))

        # if the disconnected client is the RadioPad Player, reset the current station
        if getattr(websocket, "is_radio_pad", False):
            CURRENT_STATION = None
            broadcast_all("station_playing", CURRENT_STATION)


async def switchboard_connect(
    connection: websockets.asyncio.server.ServerConnection,
    request: websockets.http11.Request,
):
    if request.path == "/health":
        return connection.respond(HTTPStatus.OK, "OK\n")

    if request.headers.get("Upgrade") is None:
        return connection.respond(
            HTTPStatus.BAD_REQUEST, "Missing websocket Upgrade header\n"
        )

    if request.headers.get("User-Agent", "").startswith("RadioPad/"):
        setattr(connection, "is_radio_pad", True)

    return None


async def main():
    stop_event = asyncio.Event()

    def ask_exit():
        stop_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, ask_exit)
    loop.add_signal_handler(signal.SIGTERM, ask_exit)

    host = os.environ.get("SWITCHBOARD_HOST", "localhost")
    port = int(os.environ.get("SWITCHBOARD_PORT", 1980))

    async with serve(
        switchboard,
        host,
        port,
        process_request=switchboard_connect,
    ) as server:
        logging.info("Switchboard running. Press Ctrl+C to stop.")
        logging.info(f"listening on {host}:{port}")
        await stop_event.wait()
        logging.info("Switchboard shutting down...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # websockets 14.0+? logs an error if a connection is opened and closed
    # before data is sent. e.g. when platforms send HEAD requests.
    # Suppress these warnings.
    logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Switchboard exited with error: {e}")
