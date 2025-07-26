#!/usr/bin/env python3

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

import os, sys
import urllib.request
import json
import asyncio
import serial_asyncio
import signal
import serial.tools.list_ports
import time
import traceback

from lib.player_mpv import MpvPlayer
from lib.client_switchboard import SwitchboardClient
from lib.interfaces import RadioPadPlayerConfig

MACROPAD = None
SWITCHBOARD = None


async def broadcast(event, data=None, audience="all"):
    """
    Broadcast an event to the macropad and/or switchboard.
    """
    if event == "station_playing":
        data = None
        # data = PLAYER.station.name if PLAYER.station else None

    message = json.dumps({"event": event, "data": data})

    if audience in ["macropad", "all"] and MACROPAD:
        try:
            MACROPAD.write((message + "\n").encode())
            await MACROPAD.drain()
        except Exception as e:
            print(f"BROADCAST: Failed to send to macropad: {e}")

    if audience in ["switchboard", "all"] and SWITCHBOARD:
        try:
            await SWITCHBOARD.send(message)
        except Exception as e:
            print(f"BROADCAST: Failed to send to switchboard: {e}")


async def cleanup():
    global PLAYER, SWITCHBOARD, MACROPAD
    print("Cleaning up before exit...")

    PLAYER.stop()
    await broadcast("station_playing")

    if SWITCHBOARD:
        try:
            await SWITCHBOARD.close()
        except Exception as e:
            print(f"Error closing SWITCHBOARD: {e}")
        SWITCHBOARD = None

    if MACROPAD:
        try:
            MACROPAD.close()
        except Exception as e:
            print(f"Error closing MACROPAD: {e}")
        MACROPAD = None


async def decode_msg(msg, source):
    """Decode a JSON message and return the event and data."""
    try:
        event, data = (lambda m: (m.get("event"), m.get("data")))(json.loads(msg))
        return event, data
    except Exception as e:
        print(f"{source}: error decoding message: {e}")
        return None, None


async def handle_event(event, data, source):
    """
    Common event handler for both macropad and switchboard events.
    """
    try:
        match event:
            case "volume":
                PLAYER.volume_up() if data == "up" else PLAYER.volume_down()
            case "station_request":
                if data:
                    station = next(
                        (s for s in RADIO_STATIONS if s["name"] == data), None
                    )
                    if station:
                        await PLAYER.play(station)
                    else:
                        print(f"WARNING: Station '{data}' not found in RADIO_STATIONS.")
                else:
                    PLAYER.stop()
                await broadcast("station_playing")
            case "station_playing" | "client_count" | "stations_url":
                pass  # ignore these events.
            case "station_list":
                if source == "MACROPAD":
                    # Send list of stations to macropad, stripping "url" key
                    stations_no_url = [
                        {k: v for k, v in station.items() if k != "url"}
                        for station in RADIO_STATIONS
                    ]
                    await broadcast(
                        "station_list", audience="macropad", data=stations_no_url
                    )
                    await asyncio.sleep(0.1)  # Handle backpressure
                    await broadcast("station_playing", audience="macropad")
            case _:
                print(f"{source}: unknown event: {event}")
    except Exception as e:
        print(f"{source}: error handling event '{event}': {e}")


async def connect_to_macropad():
    """
    Find and connect to the first available macropad data port (CDC2).
    Returns (reader, writer) tuple, or (None, None) if not found.
    """
    macropad_ports = [
        port.device
        for port in serial.tools.list_ports.comports()
        if port.interface and port.interface.startswith("CircuitPython CDC2")
    ]

    if not macropad_ports:
        print("MACROPAD: no data ports found, is it plugged in?")
        return None, None

    print(f"MACROPAD: found ports: {macropad_ports}")
    for macropad_port in macropad_ports:
        print(f"MACROPAD: attempting to connect to {macropad_port}")
        try:
            reader, writer = await serial_asyncio.open_serial_connection(
                url=macropad_port, baudrate=115200
            )
            print(f"MACROPAD: connected to: {macropad_port}")
            return reader, writer
        except Exception as e:
            print(f"MACROPAD: failed to connect to {macropad_port}: {e}")
            continue  # Try next port
    return None, None


async def macropad_message_loop(reader):
    """
    Listen for messages from the macropad and handle events.
    """
    macropad_buffer = ""
    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            macropad_buffer += line.decode("utf-8")
            while "\n" in macropad_buffer:
                msg, macropad_buffer = macropad_buffer.split("\n", 1)
                msg = msg.strip()
                if not msg:
                    continue
                try:
                    event, data = await decode_msg(msg, "MACROPAD")
                except Exception as e:
                    # partial or malformed message, continue buffering...
                    continue

                if event:
                    await handle_event(event, data, "MACROPAD")
        except Exception as e:
            print(f"MACROPAD: error reading message: {e}")
            break


async def macropad_connect_loop():
    """Connect to macropad and listen for events with auto-reconnect."""
    global MACROPAD

    while True:
        try:
            reader, writer = await connect_to_macropad()
            MACROPAD = writer

            if MACROPAD:
                # Clear all pending serial messages except the last one
                # this will preserve the last station request from macropad.
                last_line = None
                try:
                    while True:
                        line = await asyncio.wait_for(reader.readline(), timeout=0.1)
                        if not line:
                            break
                        last_line = line
                except Exception:
                    pass  # Ignore timeout or empty buffer

                # If we found any lines, keep only the last one
                if last_line:
                    # Put the last line back into the buffer for processing
                    # This works because readline() returns bytes
                    # We'll decode and process it in macropad_message_loop
                    class LastLineReader:
                        def __init__(self, last_line, reader):
                            self._last_line = last_line
                            self._reader = reader
                            self._used = False

                        async def readline(self):
                            if not self._used:
                                self._used = True
                                return self._last_line
                            return await self._reader.readline()

                    reader = LastLineReader(last_line, reader)

                # Listen for messages from macropad
                await macropad_message_loop(reader)

        except Exception as e:
            print(f"MACROPAD: Unexpected error: {e}")
        finally:
            if MACROPAD:
                try:
                    MACROPAD.close()
                    await MACROPAD.wait_closed()
                except Exception as e:
                    print(f"MACROPAD: error during wait_closed (likely unplugged): {e}")
                MACROPAD = None

        print("MACROPAD: reconnecting in 3s...")
        await asyncio.sleep(3)


def create_player_and_config():
    """
    Create and configure the PLAYER and its config,
    performing registry discovery if needed.
    Returns (PLAYER, RADIO_STATIONS).
    """
    audio_channels = os.getenv("RADIOPAD_AUDIO_CHANNELS", "stereo")
    player_id = os.getenv("RADIOPAD_PLAYER_ID", "briceburg")
    registry_url = os.getenv("RADIOPAD_REGISTRY_URL", "https://registry.radiopad.dev")
    stations_url = os.getenv("RADIOPAD_STATIONS_URL", None)
    switchboard_url = os.getenv("RADIOPAD_SWITCHBOARD_URL", None)

    def fetch_json_url(url, timeout=12, retries=3):
        for attempt in range(retries):
            try:
                req = urllib.request.Request(
                    url, headers={"Accept": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    if response.status == 200:
                        return json.loads(response.read())
                    else:
                        print(f"Failed to fetch JSON: {response.status} from {url}")
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {url}: {e}")
            print(f"Retrying in {2 ** attempt} seconds...")
            time.sleep(2**attempt)
        return None

    # Discovery logic
    if os.getenv("RADIOPAD_ENABLE_DISCOVERY", "true") == "true":
        if not player_id:
            print("RADIOPAD_PLAYER_ID must be set to enable discovery.")
            sys.exit(1)
        url = f"{registry_url.rstrip('/')}/v1/players/{player_id}"
        print(
            f"Discovering station presets and switchboard from {url} ...\n   to skip, set RADIOPAD_ENABLE_DISCOVERY=false"
        )
        data = fetch_json_url(url)
        if data:
            if not stations_url:
                stations_url = data.get("stationsUrl")
            if not switchboard_url:
                switchboard_url = data.get("switchboardUrl")
        else:
            print("Failed to discover player info from registry.")

    if not stations_url:
        print(
            "Please set RADIOPAD_STATIONS_URL or enable discovery by providing RADIOPAD_PLAYER_ID."
        )
        sys.exit(1)

    print(f"Fetching stations from {stations_url} ...")
    radio_stations = fetch_json_url(stations_url)
    if not radio_stations:
        print("Station list is empty, exiting.")
        sys.exit(1)

    # Create config and PLAYER
    player_config = RadioPadPlayerConfig(
        id=player_id,
        stations=radio_stations,
        stations_url=stations_url,
        audio_channels=audio_channels,
        registry_url=registry_url,
        switchboard_url=switchboard_url,
    )
    PLAYER = MpvPlayer(player_config)
    return PLAYER, radio_stations


# --- Usage in main script ---

if __name__ == "__main__":

    def handle_exit(signum=None, frame=None, code=0):
        print("\nPLAYER: received exit signal...")
        sys.exit(code)

    PLAYER, RADIO_STATIONS = create_player_and_config()
    SWITCHBOARD = SwitchboardClient(PLAYER)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    async def main():
        global MACROPAD, SWITCHBOARD, PLAYER
        try:
            await asyncio.gather(
                macropad_connect_loop(),
                SWITCHBOARD.run(),
            )
        except asyncio.CancelledError:
            print("\nexiting...")
            await cleanup()
            raise
        except Exception as e:
            print(f"Unexpected error in main: {e}")
            traceback.print_exc()
            await cleanup()
            raise

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
