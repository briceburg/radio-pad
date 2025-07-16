#!/usr/bin/env python

# This file is part of the radio-pad project.
# https://github.com/briceburg/radio-pad
#
# Copyright (c) 2025 Brice Burgess <https://github.com/briceburg>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import asyncio
import json
import logging
import os
import signal

import websockets
from websockets.asyncio.server import broadcast, serve
from http import HTTPStatus

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
) -> None | websockets.http11.Response:
    if request.path == "/health":
        return connection.respond(HTTPStatus.OK, "OK\n")

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

    # Suppress websocket healthcheck, connection logs.
    # https://websockets.readthedocs.io/en/stable/topics/logging.html#log-levels
    logging.getLogger("websockets.server").setLevel(logging.WARNING)

    async with serve(
        switchboard,
        os.environ.get("SWITCHBOARD_HOST", "localhost"),
        int(os.environ.get("SWITCHBOARD_PORT", 1980)),
        process_request=switchboard_connect,
    ) as server:
        logging.info("Switchboard running. Press Ctrl+C to stop.")
        logging.info(
            f"Listening on {server.sockets[0].getsockname()[0]}:{server.sockets[0].getsockname()[1]}"
        )
        await stop_event.wait()
        logging.info("Switchboard shutting down...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        logging.info("Starting switchboard... Press Ctrl+C to stop.")
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Switchboard exited with error: {e}")
