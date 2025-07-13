#!/usr/bin/env python

import asyncio
import logging
import os
import signal
import sys

import websockets
from websockets.asyncio.server import broadcast, serve

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))
from protocol import MessageProtocol, Events
from config import Config

CURRENT_STATION = None


async def switchboard(websocket):
    global CURRENT_STATION

    def broadcast_all(event: str, data):
        broadcast(websocket.server.connections, MessageProtocol.create_message(event, data))

    try:
        broadcast_all(Events.CLIENT_COUNT, len(websocket.server.connections))
        await websocket.send(MessageProtocol.create_message(Events.STATION_PLAYING, CURRENT_STATION))

        async for msg in websocket:
            is_valid, error_reason = MessageProtocol.validate_message(msg)
            if not is_valid:
                return await websocket.close(code=1007, reason=error_reason)
            
            event, data = MessageProtocol.parse_message(msg)

            if event == Events.STATION_PLAYING:
                CURRENT_STATION = data
                broadcast_all(Events.STATION_PLAYING, CURRENT_STATION)
            elif event == Events.STATION_REQUEST:
                broadcast_all(Events.STATION_REQUEST, data)
            else:
                return await websocket.close(
                    code=1007,
                    reason=f"Unknown event in message: {event}",
                )
    except websockets.exceptions.ConnectionClosedError:
        # Suppress expected disconnect errors
        pass
    finally:
        broadcast_all(Events.CLIENT_COUNT, len(websocket.server.connections))

        # if the disconnected client is the RadioPad Player, reset the current station
        if getattr(websocket, "is_radio_pad", False):
            CURRENT_STATION = None
            broadcast_all(Events.STATION_PLAYING, CURRENT_STATION)


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
        Config.SWITCHBOARD_HOST,
        Config.SWITCHBOARD_PORT,
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
