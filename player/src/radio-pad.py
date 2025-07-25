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

from python_mpv_jsonipc import MPV
import os, sys, subprocess
import urllib.request
import json
import asyncio
import websockets
import serial_asyncio
import signal
import serial.tools.list_ports
import time
import traceback

AUDIO_CHANNELS = os.getenv("RADIOPAD_AUDIO_CHANNELS", "stereo")  # 'stereo' or 'mono'
MPV_SOCKET_FILE = "/tmp/radio-pad-mpv.sock"
MACROPAD = None
SWITCHBOARD = None
STATION = None

mpv_process = None
mpv_sock = None
mpv_volume = None
mpv_sock_lock = asyncio.Lock()


async def broadcast(event, data=None, audience="all"):
    """
    Broadcast an event to the macropad and/or switchboard.
    """
    if event == "station_playing":
        data = STATION["name"] if STATION else None

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
    global mpv_process, mpv_sock, SWITCHBOARD, MACROPAD
    print("Cleaning up before exit...")

    if mpv_process or mpv_sock:
        stop_station()
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


async def play_station(station_name):
    global mpv_process, mpv_sock, STATION
    print(f"PLAYER: attempting to play station: {station_name}")
    try:
        # Stop any currently playing station
        if mpv_process:
            stop_station()

        # Find the station by name
        for station in RADIO_STATIONS:
            if station["name"] == station_name:
                STATION = station
                break

        if not STATION:
            print(f"PLAYER: station not found: {station_name}")
            return

        print(
            f"PLAYER: playing: {STATION['name']} @ {STATION['url']} ({AUDIO_CHANNELS})"
        )
        mpv_process = subprocess.Popen(
            [
                "mpv",
                STATION["url"],
                "--no-osc",
                "--no-osd-bar",
                "--no-input-default-bindings",
                "--no-input-cursor",
                "--no-input-vo-keyboard",
                "--no-input-terminal",
                "--no-audio-display",
                f"--input-ipc-server={MPV_SOCKET_FILE}",
                "--no-video",
                "--no-cache",
                "--stream-lavf-o=reconnect_streamed=1",
                "--profile=low-latency",
                f"--audio-channels={AUDIO_CHANNELS}",
            ],
            stdin=subprocess.DEVNULL,
            stdout=sys.stdout,
            stderr=subprocess.STDOUT,
        )
        # Reset mpv_sock so a new one will be created for the new process
        mpv_sock = None
        await establish_ipc_socket()
    except Exception as e:
        print(f"PLAYER: error starting station: {e}")


def stop_station():
    global mpv_process, mpv_sock, STATION
    STATION = None

    if mpv_sock:
        try:
            mpv_sock.stop()
        except Exception as e:
            pass
        finally:
            mpv_sock = None

    if mpv_process:
        try:
            mpv_process.terminate()
            if os.path.exists(MPV_SOCKET_FILE):
                os.remove(MPV_SOCKET_FILE)
        except Exception as e:
            pass
        finally:
            mpv_process = None


async def volume_adjust(amt):
    global mpv_sock
    global mpv_volume
    if mpv_sock is None:
        print("PLAYER: mpv IPC socket not established, cannot adjust volume.")
        return

    if mpv_volume is None:
        mpv_volume = mpv_sock.volume

    volume = mpv_volume + amt

    # keep volume from getting too high or too low
    if volume > 100:
        volume = 100
    elif volume < 50:
        volume = 50

    mpv_volume = volume
    mpv_sock.volume = mpv_volume
    print(f"  Adjusted Volume: {mpv_volume}")


async def establish_ipc_socket():
    global mpv_sock
    async with mpv_sock_lock:
        if mpv_sock is not None:
            return mpv_sock
        loop = asyncio.get_running_loop()
        for i in range(20):
            try:
                # Run the blocking MPV constructor in a thread pool
                sock = await loop.run_in_executor(
                    None, lambda: MPV(start_mpv=False, ipc_socket=MPV_SOCKET_FILE)
                )
                mpv_sock = sock
                print("mpv IPC established.")
                # Restore previously set volume if available
                if mpv_volume is not None:
                    print(f"Restoring volume to {mpv_volume}.")
                    try:
                        mpv_sock.volume = mpv_volume
                    except Exception as e:
                        print(f"Failed restoring volume: {e}")
                return mpv_sock
            except Exception as e:
                if i == 19:
                    print(f"Failed to connect to mpv IPC socket: {e}")
                await asyncio.sleep(0.1)
        print("failed to establish mpv IPC. volume controls disabled")
        mpv_sock = None
        return None

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
                await volume_adjust(5 if data == "up" else -5)
            case "station_request":
                if data:
                    await play_station(data)
                else:
                    stop_station()
                await broadcast("station_playing")
            case "station_playing" | "client_count" | "station_url":
                pass  # ignore these events.
            case "station_list":
                if source == "MACROPAD":
                    # Send list of stations to macropad, stripping "url" key
                    stations_no_url = [
                        {k: v for k, v in station.items() if k != "url"}
                        for station in RADIO_STATIONS
                    ]
                    await broadcast("station_list", audience="macropad", data=stations_no_url)
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

async def switchboard_message_loop(ws):
    """
    Listen for messages from the switchboard and handle events.
    """
    async for msg in ws:
        try:
            event, data = await decode_msg(msg, "SWITCHBOARD")
            if event:
                await handle_event(event, data, "SWITCHBOARD")
        except Exception as e:
            print(f"SWITCHBOARD: error handling event: {e}")


async def switchboard_connect_loop(url):
    """Connect to switchboard and listen for events with auto-reconnect."""
    global SWITCHBOARD

    if not url:
        print("SWITCHBOARD_URL is empty, skipping switchboard connection.")
        return

    while True:
        try:
            headers = {
                "User-Agent": "RadioPad/1.0",
                "RadioPad-Stations-Url": STATIONS_URL,
            }
            async with websockets.connect(url, additional_headers=headers) as ws:
                print(f"SWITCHBOARD: connected to: {url}")
                SWITCHBOARD = ws

                # let the switchboard know what current station is playing. 
                asyncio.create_task(broadcast("station_playing", audience="switchboard"))

                # begin listening for messages
                await switchboard_message_loop(ws)

        except (ConnectionRefusedError, OSError) as e:
            print(f"SWITCHBOARD: failed to connect to {url}: {e}")
            print(
                "If this is the wrong URL, please set the SWITCHBOARD_URL environment variable."
            )
        except Exception as e:
            print(f"SWITCHBOARD: Unexpected error: {e}")
        finally:
            if SWITCHBOARD:
                try:
                    await SWITCHBOARD.close()
                    print("SWITCHBOARD: websocket connection closed.")
                except Exception as e:
                    print(f"Error closing SWITCHBOARD: {e}")
                SWITCHBOARD = None
        print("reconnecting to switchboard in 5s...")
        await asyncio.sleep(5)
        

async def main():
    try:
        await asyncio.gather(
            macropad_connect_loop(),
            switchboard_connect_loop(SWITCHBOARD_URL),
        )
    except asyncio.CancelledError:
        print("\nPLAYER: exiting...")
        await cleanup()
        raise
    except Exception as e:
        print(f"Unexpected error in main: {e}")
        traceback.print_exc()
        await cleanup()
        raise


if __name__ == "__main__":

    PLAYER_ID = os.getenv("RADIOPAD_PLAYER_ID", "briceburg")
    REGISTRY_URL = os.getenv(
        "RADIOPAD_REGISTRY_URL",
        "https://registry.radiopad.dev",
    )
    STATIONS_URL = os.getenv("RADIOPAD_STATIONS_URL", None)
    SWITCHBOARD_URL = os.getenv("RADIOPAD_SWITCHBOARD_URL", None)

    def fetch_json_url(url, timeout=12, retries=3):
        """Fetch JSON from a URL with retries and a timeout."""
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers={"Accept": "application/json"})
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

    if os.getenv("RADIOPAD_ENABLE_DISCOVERY", "true") == "true":
        if not PLAYER_ID:
            print("RADIOPAD_PLAYER_ID must be set to enable discovery.")
            sys.exit(1)
        url = f"{REGISTRY_URL.rstrip('/')}/v1/players/{PLAYER_ID}"
        print(
            f"Discovering station presets and switchboard from {url} ...\n   to skip, set RADIOPAD_ENABLE_DISCOVERY=false"
        )
        data = fetch_json_url(url)
        if data:
            if not STATIONS_URL:
                STATIONS_URL = data.get("stationsUrl")
            if not SWITCHBOARD_URL:
                SWITCHBOARD_URL = data.get("switchboardUrl")
        else:
            print("Failed to discover player info from registry.")

    if not STATIONS_URL:
        print(
            "Please set RADIOPAD_STATIONS_URL or enable discovery by providing RADIOPAD_PLAYER_ID."
        )
        sys.exit(1)

    print(f"Fetching stations from {STATIONS_URL} ...")
    RADIO_STATIONS = fetch_json_url(STATIONS_URL)
    if not RADIO_STATIONS:
        print("Station list is empty, exiting.")
        sys.exit(1)

    def handle_exit(signum=None, frame=None, code=0):
        print("\nPLAYER: received exit signal...")
        sys.exit(code)

    try:
        signal.signal(signal.SIGTERM, handle_exit)
        signal.signal(signal.SIGINT, handle_exit)
        asyncio.run(main())
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
