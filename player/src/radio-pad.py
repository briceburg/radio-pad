#!/usr/bin/env python3
from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import PromptSession
from python_mpv_jsonipc import MPV
import os, sys, subprocess
import urllib.request
import json
from time import sleep
import asyncio
import websockets

AUDIO_CHANNELS = os.getenv("AUDIO_CHANNELS", "stereo")  # 'stereo' or 'mono'
MPV_SOCKET_FILE = "/tmp/radio-pad-mpv.sock"
RADIO_STATIONS_FILE = "/tmp/radio-pad-stations.json"
RADIO_STATIONS_URL = os.getenv(
    "RADIO_STATIONS_URL",
    "https://raw.githubusercontent.com/briceburg/radio-pad/refs/heads/main/src/stations.json",
)
STATIONS_PER_PAGE = 12  # align this with MACROPAD_KEY_COUNT

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

bindings = KeyBindings()
mpv_process = None
mpv_sock = None
mpv_volume = None
mpv_sock_lock = asyncio.Lock()


def char_to_index(ch):
    """
    Convert a single character to an integer index:
    '0'-'9' -> 0-9, 'a'-'z' -> 10-35.
    """
    if ch.isdigit():
        return int(ch)
    elif "a" <= ch <= "z":
        return 10 + ord(ch) - ord("a")
    else:
        return None


def stop_station():
    global mpv_process
    global mpv_sock

    if mpv_sock:
        try:
            mpv_sock.stop()
        except Exception as e:
            print(f"error stopping ipc: {e}")
        finally:
            mpv_sock = None

    if mpv_process:
        try:
            mpv_process.terminate()
            if os.path.exists(MPV_SOCKET_FILE):
                os.remove(MPV_SOCKET_FILE)
        except Exception as e:
            print(f"error terminating mpv: {e}")
        finally:
            mpv_process = None


def play_station(station_index):
    global mpv_process, mpv_sock
    station = RADIO_STATIONS[station_index]
    if mpv_process:
        print("Stopping current station...")
        stop_station()
    print(f"Playing {station['name']} from {station['url']} as {AUDIO_CHANNELS}.")
    mpv_process = subprocess.Popen(
        [
            "mpv",
            station["url"],
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
    # Start IPC connection asynchronously (does not block)
    asyncio.create_task(establish_ipc_socket())

    # send station playing event to switchboard
    if "switchboard_ws" in globals() and switchboard_ws is not None:
        msg = json.dumps({"key": "station_playing", "data": station["name"]})
        asyncio.create_task(switchboard_ws.send(msg))


async def establish_ipc_socket():
    global mpv_sock
    async with mpv_sock_lock:
        if mpv_sock is not None:
            return mpv_sock
        loop = asyncio.get_running_loop()
        for _ in range(20):
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
            except Exception:
                await asyncio.sleep(0.1)
        print("failed to establish mpv IPC. volume controls disabled")
        mpv_sock = None
        return None


def volume_adjust(amt):
    global mpv_sock
    global mpv_volume
    if mpv_sock is None:
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


@bindings.add("c-@", "<any>", "<any>", record_in_macro=False)
def _(event):
    """
    listen for control events, control character is Ctrl+@ followed by 2 keypresses.
      [Ctrl+@, V, +] increase volume
      [Ctrl+@, V, -] decrease volume
      [Ctrl+@, X, *] stop station
      [Ctrl+@, 0, 3] play 4th station
    """
    cmd_char = event.key_sequence[-2].data
    arg_char = event.key_sequence[-1].data

    match cmd_char:
        case "V":
            volume_adjust(-5) if arg_char == "-" else volume_adjust(5)
        case "X":
            stop_station()
        case _:
            page_idx = char_to_index(cmd_char)
            station_idx = page_idx * STATIONS_PER_PAGE + char_to_index(arg_char)
            play_station(station_idx)


async def start_switchboard(url):
    async with websockets.connect(url, user_agent_header="RadioPad/1.0") as ws:
        # expose the switchboard websocket globally (so play_station can send messages)
        global switchboard_ws
        switchboard_ws = ws

        # Listen for station requests
        async for message in ws:
            try:
                print(f"Received message from switchboard: {message}")
                # event = json.loads(message)
                # key, value = event.get("key"), event.get("data")
                # if key == "station_request":
                #     print(f"Received remote station request: {value}")
                #     # Find and play the requested station by name
                #     for idx, station in enumerate(RADIO_STATIONS):
                #         if station["name"] == value:
                #             play_station(idx)
                #             break
                #     else:
                #         print(f"Station '{value}' not found.")
            except Exception as e:
                print(f"Error handling switchboard message: {e}")


async def main():
    switchboard_task = asyncio.create_task(
        start_switchboard("wss://radioswitchboard.share.zrok.io")
    )
    while True:
        try:
            print("Press 'Control + @' followed by the radio page and station id.")
            print("Press 'Control + C' or 'Control + D' to exit.")
            await session.prompt_async()
        except (KeyboardInterrupt, EOFError):
            print("Exiting...")
            stop_station()
            sys.exit(0)
        except Exception as e:
            print(f"Unhandled exception: {e}")
            continue


if __name__ == "__main__":
    session = PromptSession(key_bindings=bindings)
    asyncio.run(main())
