#!/usr/bin/env python

import asyncio
import json
import logging
import os
import signal

import websockets
from websockets.asyncio.server import broadcast, serve

CURRENT_STATION = None


def mkevent(event: str, data) -> str:
    """Create an event message in event:data format."""
    return f"{event}:{data}"


async def switchboard(websocket):
    global CURRENT_STATION

    def broadcast_all(event: str, data):
        broadcast(websocket.server.connections, mkevent(event, data))

    try:
        broadcast_all("client_count", len(websocket.server.connections))
        await websocket.send(mkevent("station_playing", CURRENT_STATION))

        async for message in websocket:
            event, _, data = message.partition(":")
            if not event:
                return await websocket.close(
                    code=1007,
                    reason='Invalid message format. Expect "event:data"',
                )
            if event == "station_playing":
                CURRENT_STATION = data
                broadcast_all("station_playing", CURRENT_STATION)
            elif event == "station_request":
                broadcast_all("station_request", data)
            else:
                return await websocket.close(
                    code=1007,
                    reason=f"Unknown event: {event}",
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


async def switchboard_connect(connection, request):
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

    async with serve(
        switchboard,
        os.environ.get("SWITCHBOARD_HOST", "localhost"),
        int(os.environ.get("SWITCHBOARD_PORT", 1980)),
        process_request=switchboard_connect,
    ) as server:
        logging.info("Switchboard running. Press Ctrl+C to stop.")
        await stop_event.wait()
        logging.info("Switchboard shutting down...")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        logging.info("Starting switchboard... Press Ctrl+C to stop.")
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Switchboard exited with error: {e}")
