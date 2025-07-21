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
from collections import defaultdict

import websockets
from websockets.asyncio.server import broadcast, serve, ServerConnection
from http import HTTPStatus

CURRENT_STATION_BY_HOST = defaultdict(lambda: None)
PARTITION_ENABLED = os.environ.get("SWITCHBOARD_PARTITION_BY_HTTP_HOST") == "true"
WEBSOCKETS_BY_HOST = defaultdict(set)


def get_host_key(websocket) -> str:
    """Returns the host key for a given websocket, or '_global' if partitioning is disabled."""
    if not PARTITION_ENABLED:
        return "_global"
    return getattr(websocket, "host", None)


async def switchboard(websocket):
    host_key = get_host_key(websocket)

    def mkmsg(event: str, data=None) -> str:
        if data is None:
            if event == "station_playing":
                data = CURRENT_STATION_BY_HOST[host_key]
            elif event == "client_count":
                data = len(get_connections())

        return json.dumps({"event": event, "data": data})

    def get_connections():
        return WEBSOCKETS_BY_HOST.get(host_key, set())

    def broadcast_all(event: str, data=None):
        connections = get_connections()
        if connections:
            broadcast(connections, mkmsg(event, data))

    try:
        broadcast_all("client_count")
        await websocket.send(mkmsg("station_playing"))

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
                CURRENT_STATION_BY_HOST[host_key] = data
                broadcast_all("station_playing")
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
        if websocket in WEBSOCKETS_BY_HOST[host_key]:
            WEBSOCKETS_BY_HOST[host_key].remove(websocket)
        if not WEBSOCKETS_BY_HOST[host_key]:
            del WEBSOCKETS_BY_HOST[host_key]

        broadcast_all("client_count")

        # if the disconnected client is the RadioPad Player, reset the current station
        if getattr(websocket, "is_radio_pad", False):
            CURRENT_STATION_BY_HOST[host_key] = None
            broadcast_all("station_playing")


async def switchboard_connect(
    connection: ServerConnection,
    request: websockets.http11.Request,
) -> None | websockets.http11.Response:
    if request.path == "/healthz":
        return connection.respond(HTTPStatus.OK, "OK\n")

    if PARTITION_ENABLED:
        host = request.headers.get("Host")
        if not host:
            return connection.respond(
                HTTPStatus.BAD_REQUEST,
                "Host header required, partitioning is enabled.\n",
            )
        host = host.split(":")[0].lower()  # strip port and normalize
        setattr(connection, "host", host)
        WEBSOCKETS_BY_HOST[host].add(connection)
    else:
        # When not partitioning, all connections go into the _global set
        WEBSOCKETS_BY_HOST["_global"].add(connection)

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
        if PARTITION_ENABLED:
            logging.info("Partitioning by HTTP host is enabled.")
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
