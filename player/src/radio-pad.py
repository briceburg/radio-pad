#!/usr/bin/env python3
from python_mpv_jsonipc import MPV
import os, sys, subprocess
import urllib.request
import json
from time import sleep
import asyncio
import websockets
import serial
import signal
import serial.tools.list_ports

AUDIO_CHANNELS = os.getenv("AUDIO_CHANNELS", "stereo")  # 'stereo' or 'mono'
MPV_SOCKET_FILE = "/tmp/radio-pad-mpv.sock"
RADIO_STATIONS_FILE = "/tmp/radio-pad-stations.json"
RADIO_STATIONS_URL = os.getenv(
    "RADIO_STATIONS_URL",
    "https://raw.githubusercontent.com/briceburg/radio-pad/refs/heads/main/player/stations.json",
)
MACROPAD = None
SWITCHBOARD =None
STATION = None

# cache radio stations
if not os.path.exists(RADIO_STATIONS_FILE):
    try:
        print(f"Downloading radio stations from {RADIO_STATIONS_URL} ...")
        urllib.request.urlretrieve(RADIO_STATIONS_URL, RADIO_STATIONS_FILE)
    except Exception as e:
        print(f"Error downloading radio stations: {e}")
        sys.exit(1)

with open(RADIO_STATIONS_FILE, "r") as f:
    try:
        RADIO_STATIONS = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing radio stations JSON: {e}")
        sys.exit(1)

mpv_process = None
mpv_sock = None
mpv_volume = None
mpv_sock_lock = asyncio.Lock()

def broadcast(event, data=None, audience="all"):
    """
    Broadcast an event to the macropad and/or switchboard.
    """
    if not data:
        if event == "station_playing":
            data = STATION["name"] if STATION else None

    msg = json.dumps({"event": event, "data": data})

    if audience in ["macropad", "all"] and MACROPAD:
        print(f"BROADCAST: macropad: {event}")
        MACROPAD.write((msg + "\n").encode())  # <-- Add newline here

    if audience in ["switchboard", "all"] and SWITCHBOARD:
        print(f"BROADCAST: switchboard: {event}")
        asyncio.create_task(SWITCHBOARD.send(msg))

def cleanup():
    global  mpv_process, mpv_sock, SWITCHBOARD, MACROPAD
    if SWITCHBOARD:
        try:
            asyncio.get_event_loop().run_until_complete(SWITCHBOARD.close())
            print("SWITCHBOARD: websocket connection closed.")
        except Exception as e:
            print(f"Error closing SWITCHBOARD: {e}")
        SWITCHBOARD = None
    if MACROPAD:
        try:
            MACROPAD.close()
            print("MACROPAD: serial connection closed.")
        except Exception as e:
            print(f"Error closing MACROPAD: {e}")
        MACROPAD = None

    if mpv_process or mpv_sock:
        stop_station()

async def play_station(station_name):
    global mpv_process, mpv_sock, STATION
    try:
        # Find the station by name
        for station in RADIO_STATIONS:
            if station["name"] == station_name:
                STATION = station
                break

        if not STATION:
            print(f"PLAYER: station not found: {station_name}")
            return

        # Stop any currently playing station
        if mpv_process:
            stop_station()

        print(f"PLAYER: playing: {STATION['name']} @ {STATION['url']} ({AUDIO_CHANNELS})")
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

        # broadcast station
        broadcast("station_playing")
    except Exception as e:
        print(f"PLAYER: error starting station: {e}")

def stop_station():
    global mpv_process
    global mpv_sock

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

def volume_adjust(amt):
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


async def switchboard_connect_and_listen(url):
    print(f"Connecting to switchboard at {url} ...")
    async with websockets.connect(url, user_agent_header="RadioPad/1.0") as ws:
        # expose the switchboard websocket globally (so play_station can send messages)
        global SWITCHBOARD
        SWITCHBOARD = ws
        
        print(f"SWITCHBOARD: connected to: {url}")

        # Send initial station playing event
        broadcast("station_playing", audience="switchboard")

        # Listen for station requests
        async for message in ws:
            try:
                msg = json.loads(message)
                event, data = msg.get("event"), msg.get("data")
                if event == "station_request":
                    print(f"SWITCHBOARD: station request: {data}")
                    asyncio.create_task(play_station(data))
                if event == "station_playing":
                    # TODO: support multiple players by player_id/UA 
                    continue  # Ignore this event
                if event == "client_count":
                    continue
                else:
                    print(f"SWITCHBOARD: unknown event: {event}")
            except Exception as e:
                print(f"SWITCHBOARD: error: {e}")

def macropad_connect_and_listen(loop):
    """Connect to the macropad serial port."""
    global MACROPAD
    MACROPAD = None
    ports = serial.tools.list_ports.comports()
    for port, desc, _ in sorted(ports):
        if "Macropad" in desc:
            try:
                MACROPAD = serial.Serial(port, 115200, timeout=1) 
            except serial.SerialException as e:
                if e.errno != 16:  # Device or resource busy
                    print(f"Serial error on {port}: {e}")
    if MACROPAD is None:
        return False

    print(f"MACROPAD: connected to: {MACROPAD.portstr}")
    broadcast("station_playing", audience="macropad")

    while True:
        if MACROPAD.in_waiting > 0:
            msg = MACROPAD.read(MACROPAD.in_waiting).decode('utf-8').strip()
            event, data = msg.split(":", 1) if ":" in msg else (msg, None)
            match event:
                case "volume":
                    volume_adjust(5 if data == "up" else -5)
                case "stop":
                    stop_station()
                case "play":
                    if data:
                        asyncio.run_coroutine_threadsafe(play_station(data), loop)
                case _:
                    print(f"MACROPAD: unknown event: {event}")

async def macropad_loop():
    global MACROPAD
    loop = asyncio.get_running_loop()
    while True:
        try:
            await loop.run_in_executor(None, macropad_connect_and_listen, loop)
        except Exception as e:
            print(f"Macropad error: {e}")
        finally:
            if MACROPAD:
                try:
                    MACROPAD.close()
                    print("MACROPAD: serial connection closed.")
                except Exception as e:
                    print(f"Error closing MACROPAD: {e}")
                MACROPAD = None
        print("PLAYER: reconnecting to macropad in 10s...")
        await asyncio.sleep(10)

async def switchboard_loop(url):
    if url == "":
        print("SWITCHBOARD: URL is empty, skipping switchboard connection.")
        return
    global SWITCHBOARD
    while True:
        try:
            await switchboard_connect_and_listen(url)
        except Exception as e:
            print(f"Switchboard error: {e}")
        finally:
            if SWITCHBOARD:
                try:
                    await SWITCHBOARD.close()
                    print("SWITCHBOARD: websocket connection closed.")
                except Exception as e:
                    print(f"Error closing SWITCHBOARD: {e}")
                SWITCHBOARD = None
        print("PLAYER: reconnecting to switchboard in 5s...")
        await asyncio.sleep(5)

async def main():
    await asyncio.gather(
        macropad_loop(),
        switchboard_loop(os.getenv("SWITCHBOARD_URL", "ws://localhost:1980/")),
    )

if __name__ == "__main__":
    def handle_exit(signum=None, frame=None, code=0):
        print("\nPLAYER: exiting...")
        cleanup()
        sys.exit(code)

    try:
        signal.signal(signal.SIGTERM, handle_exit)
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        handle_exit()
    except Exception as e:
        print(f"Unexpected error: {e}")
        handle_exit(code=1)