#!/usr/bin/env python

import asyncio
import json
import logging
import os

from websockets.asyncio.server import broadcast, serve

CURRENT_STATION = None
SERVER = None

def kv(key, data):
    return json.dumps({"key": key, "data": data})


def client_count_event():
    count = len(SERVER.connections) if SERVER else 0
    return kv("client_count", count)


def station_playing_event():
    return kv("station_playing", CURRENT_STATION)


def station_request_event(station):
    return kv("station_request", station)


async def switchboard(websocket):
    global CURRENT_STATION
    try:
        broadcast(SERVER.connections, client_count_event())

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
                broadcast(SERVER.connections, station_playing_event())
            elif key == "station_request":
                broadcast(SERVER.connections, station_request_event(value))
            else:
                return await websocket.close(
                    code=1007,
                    reason=f"Unknown key in message: {key}",
                )
    except Exception as e:
        logging.error(f"Closing connection, exception: {e}")
        await websocket.close(
            code=1011,
            reason=f"Internal server error: {str(e)}",
        )
    finally:
        broadcast(SERVER.connections, client_count_event())


async def main():
    global SERVER
    async with serve(
        switchboard,
        os.environ.get("SWITCHBOARD_HOST", "localhost"),
        int(os.environ.get("SWITCHBOARD_PORT", 1980)),
    ) as server:
        SERVER = server
        await server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        logging.info("Starting switchboard... Press Ctrl+C to stop.")
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("...switchboard stopped.")
