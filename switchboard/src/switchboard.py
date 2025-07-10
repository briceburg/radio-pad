#!/usr/bin/env python

import asyncio
import json
import logging
import os

from websockets.asyncio.server import broadcast, serve

CURRENT_STATION = None


def mkevent(event: str, data) -> str:
    """Create a JSON event message."""
    return json.dumps({"event": event, "data": data})


async def switchboard(websocket):
    global CURRENT_STATION

    def broadcast_all(event: str, data):
        broadcast(websocket.server.connections, mkevent(event, data))

    try:
        broadcast_all("client_count", len(websocket.server.connections))
        await websocket.send(mkevent("station_playing", CURRENT_STATION))

        async for message in websocket:
            try:
                msg = json.loads(message)
                event, data = msg.get("event"), msg.get("data")
            except json.JSONDecodeError:
                return await websocket.close(
                    code=1007,
                    reason='Invalid message format. Expect JSON {"event": ..., "data": ...}',
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
    finally:
        broadcast_all("client_count", len(websocket.server.connections))

        # if the disconnected client is the RadioPad Player, reset the current station
        if getattr(websocket, "is_radio_pad", False):
            CURRENT_STATION = None
            broadcast_all("station_playing", CURRENT_STATION)


async def switchboard_connect(connection, request):
    if request.headers.get("User-Agent", "").startswith("RadioPad/"):
        setattr(connection, "is_radio_pad", True)
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
