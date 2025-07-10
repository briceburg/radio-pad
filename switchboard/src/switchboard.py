#!/usr/bin/env python

import asyncio
import json
import logging
import os

from websockets.asyncio.server import broadcast, serve

CURRENT_STATION = None


def kv(key, data):
    return json.dumps({"key": key, "data": data})


def client_count_event(count):
    return kv("client_count", count)


def station_playing_event():
    return kv("station_playing", CURRENT_STATION)


def station_request_event(station):
    return kv("station_request", station)


async def switchboard(websocket):
    global CURRENT_STATION
    try:
        broadcast(
            websocket.server.connections,
            client_count_event(len(websocket.server.connections)),
        )

        # Send current station to connecting client
        await websocket.send(station_playing_event())

        # Manage state changes
        async for message in websocket:
            try:
                event = json.loads(message)
                key, value = event.get("key"), event.get("data")
            except json.JSONDecodeError:
                return await websocket.close(
                    code=1007,
                    reason='Invalid message format. Expect JSON {"key": ..., "data": ...}',
                )
            if key == "station_playing":
                CURRENT_STATION = value
                broadcast(websocket.server.connections, station_playing_event())
            elif key == "station_request":
                broadcast(websocket.server.connections, station_request_event(value))
            else:
                return await websocket.close(
                    code=1007,
                    reason=f"Unknown key in message: {key}",
                )
    finally:
        broadcast(
            websocket.server.connections,
            client_count_event(len(websocket.server.connections)),
        )
        if websocket.is_radio_pad:
            CURRENT_STATION = None
            broadcast(websocket.server.connections, station_playing_event())


async def switchboard_connect(connection, request):
    connection.is_radio_pad = request.headers.get("User-Agent", "").startswith(
        "RadioPad/"
    )
    return None


async def main():
    async with serve(
        switchboard,
        os.environ.get("SWITCHBOARD_HOST", "localhost"),
        int(os.environ.get("SWITCHBOARD_PORT", 1980)),
        process_request=switchboard_connect,
    ) as server:
        await server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        logging.info("Starting switchboard... Press Ctrl+C to stop.")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("...switchboard stopped.")
