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
from http import HTTPStatus

import websockets
from websockets.asyncio.server import ServerConnection, broadcast, serve

CURRENT_STATION_BY_PLAYER = defaultdict(lambda: None)
STATIONS_URL_BY_PLAYER = defaultdict(lambda: None)
WEBSOCKETS_BY_PLAYER = defaultdict(set)
LOGGER = logging.getLogger("switchboard")


def get_connections(player_key: str) -> set:
    return WEBSOCKETS_BY_PLAYER.get(player_key, set())


def mkmsg(player_key: str, event: str, data=None) -> str:
    if data is None:
        if event == "station_playing":
            data = CURRENT_STATION_BY_PLAYER[player_key]
        elif event == "client_count":
            data = len(get_connections(player_key))
    return json.dumps({"event": event, "data": data})


def broadcast_all(player_key: str, event: str, data=None) -> None:
    connections = get_connections(player_key)
    if connections:
        broadcast(connections, mkmsg(player_key, event, data))


async def switchboard(websocket):
    player_key = getattr(websocket, "player_key", None)
    if not player_key:
        return await websocket.close(code=1008, reason="Missing player identifier.")

    # Track this established WebSocket connection.
    WEBSOCKETS_BY_PLAYER[player_key].add(websocket)

    try:
        broadcast_all(player_key, "client_count")
        await websocket.send(mkmsg(player_key, "station_playing"))
        await websocket.send(
            mkmsg(player_key, "stations_url", STATIONS_URL_BY_PLAYER[player_key])
        )

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
                CURRENT_STATION_BY_PLAYER[player_key] = data
                broadcast_all(player_key, "station_playing")
            elif event == "station_request":
                broadcast_all(player_key, "station_request", data)
            else:
                return await websocket.close(
                    code=1007,
                    reason=f"Unknown event in message: {event}",
                )
    except websockets.exceptions.ConnectionClosedError:
        # Suppress expected disconnect errors
        pass
    finally:
        if websocket in WEBSOCKETS_BY_PLAYER[player_key]:
            WEBSOCKETS_BY_PLAYER[player_key].remove(websocket)
        if not WEBSOCKETS_BY_PLAYER[player_key]:
            del WEBSOCKETS_BY_PLAYER[player_key]

        broadcast_all(player_key, "client_count")

        # if the disconnected client is the RadioPad Player, reset the current station
        if getattr(websocket, "is_radio_pad", False):
            CURRENT_STATION_BY_PLAYER[player_key] = None
            broadcast_all(player_key, "station_playing")
            LOGGER.info(f"RadioPad Player disconnected: {player_key}")


async def switchboard_connect(
    connection: ServerConnection,
    request: websockets.http11.Request,
) -> None | websockets.http11.Response:
    if request.path == "/healthz":
        return connection.respond(HTTPStatus.OK, "OK\n")

    # Require a WebSocket upgrade to proceed with handshake
    if not (
        request.headers.get("Upgrade", "").lower() == "websocket"
        and "upgrade" in request.headers.get("Connection", "").lower()
    ):
        return connection.respond(
            HTTPStatus.UPGRADE_REQUIRED,
            "WebSocket upgrade required for this endpoint.\n",
        )

    # Require account_id and player_id in the path
    try:
        account_id, player_id = request.path.strip("/").split("/")
        # TODO: validate account_id/player_id authn from registry
    except ValueError:
        return connection.respond(
            HTTPStatus.BAD_REQUEST,
            "Invalid path. Expected /{account_id}/{player_id}.\n",
        )

    player_key = f"{account_id}/{player_id}"
    setattr(connection, "player_key", player_key)

    if request.headers.get("User-Agent", "").startswith("RadioPad/"):
        setattr(connection, "is_radio_pad", True)

        stations_url = request.headers.get("RadioPad-Stations-Url")
        if not stations_url:
            return connection.respond(
                HTTPStatus.BAD_REQUEST,
                "RadioPad-Stations-Url header required for RadioPad Player connections.\n",
            )

        if STATIONS_URL_BY_PLAYER[player_key] != stations_url:
            STATIONS_URL_BY_PLAYER[player_key] = stations_url
            try:
                broadcast_all(player_key, "stations_url", stations_url)
            except Exception as e:
                LOGGER.error(
                    f"Failed to broadcast stations_url update for {player_key}: {e}"
                )

        LOGGER.info(
            f"RadioPad Player connected ({player_key}) with stations URL: {stations_url}"
        )

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
        LOGGER.info("Switchboard running. Press Ctrl+C to stop.")
        LOGGER.info(
            f"Listening on {server.sockets[0].getsockname()[0]}:{server.sockets[0].getsockname()[1]}"
        )
        await stop_event.wait()
        LOGGER.info("Switchboard shutting down...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        LOGGER.info("Starting switchboard... Press Ctrl+C to stop.")
        asyncio.run(main())
    except Exception as e:
        LOGGER.error(f"Switchboard exited with error: {e}")
