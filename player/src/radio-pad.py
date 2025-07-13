#!/usr/bin/env python3
from python_mpv_jsonipc import MPV
import os, sys, subprocess
import urllib.request
import json
import asyncio
import websockets
import serial_asyncio
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
SWITCHBOARD = None
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
            await MACROPAD.wait_closed()
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


async def handle_msg(msg, source):
    """
    Common event handler for both macropad and switchboard events.
    """
    try:
        event, data = (lambda m: (m.get("event"), m.get("data")))(json.loads(msg))
        
        match event:
            case "volume":
                await volume_adjust(5 if data == "up" else -5)
            case "station_request":
                if data:
                    await play_station(data)
                else:
                    stop_station()
                await broadcast("station_playing")
            case "station_playing" | "client_count":
                pass # ignore these events.
            case _:
                print(f"{source}: unknown event: {event}")
    except json.JSONDecodeError as e:
        print(f"{source}: error parsing JSON message: {e}")
    except Exception as e:
        print(f"{source}: error handling event '{event}': {e}")

async def macropad_loop():
    """Connect to macropad and listen for events with auto-reconnect."""
    global MACROPAD
    
    while True:
        try:
            # Find all macropad ports
            ports = serial.tools.list_ports.comports()
            macropad_ports = []
            for port, desc, _ in sorted(ports):
                if "Macropad" in desc:
                    macropad_ports.append(port)
            
            if not macropad_ports:
                print("MACROPAD: no ports found, is it plugged in?")
            else:
                print(f"MACROPAD: found {len(macropad_ports)} macropad port(s): {macropad_ports}")
                
                # Try each port to find the one that works for USB CDC data
                connected = False
                for macropad_port in macropad_ports:
                    print(f"MACROPAD: attempting to connect to {macropad_port}")
                    
                    try:
                        reader, writer = await serial_asyncio.open_serial_connection(
                            url=macropad_port,
                            baudrate=115200
                        )
                        
                        MACROPAD = writer
                        print(f"MACROPAD: connected to: {macropad_port}")
                        
                        # Send initial station playing event
                        await broadcast("station_playing", audience="macropad")
                        
                        # Listen for messages
                        connected = True
                        while True:
                            try:
                                line = await reader.readline()
                                if not line:
                                    break
                                
                                message = line.decode('utf-8').strip()
                                if message:
                                    await handle_msg(message, "MACROPAD")
                                    
                            except Exception as e:
                                print(f"MACROPAD: error reading message: {e}")
                                break
                                
                    except Exception as e:
                        print(f"MACROPAD: failed to connect to {macropad_port}: {e}")
                        continue  # Try next port
                    finally:
                        if MACROPAD:
                            MACROPAD.close()
                            await MACROPAD.wait_closed()
                            MACROPAD = None
                            print("MACROPAD: connection closed")
                    
                    # If we successfully connected and then disconnected, break out of port loop
                    if connected:
                        break
                
                if not connected:
                    print("MACROPAD: failed to connect to any macropad port")
                        
        except Exception as e:
            print(f"MACROPAD: Unexpected error: {e}")
        
        print("MACROPAD: reconnecting in 10s...")
        await asyncio.sleep(10)


async def switchboard_loop(url):
    """Connect to switchboard and listen for events with auto-reconnect."""
    global SWITCHBOARD

    if url == "":
        print("SWITCHBOARD: URL is empty, skipping switchboard connection.")
        return
    
    while True:
        try:
            async with websockets.connect(url, user_agent_header="RadioPad/1.0") as ws:
                print(f"SWITCHBOARD: connected to: {url}")
                # expose the switchboard websocket globally
                SWITCHBOARD = ws

                # Send initial station playing event -> TODO can we limit this to this websocket?
                await broadcast("station_playing", audience="switchboard")

                # Listen for station requests
                async for msg in ws:
                    await handle_msg(msg, "SWITCHBOARD")
        except (ConnectionRefusedError, OSError) as e:
            print(f"SWITCHBOARD: failed to connect to {url}: {e}")
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
            macropad_loop(),
            switchboard_loop(os.getenv("SWITCHBOARD_URL", "ws://localhost:1980/")),
        )
    except asyncio.CancelledError:
        print("\nPLAYER: exiting...")
        await cleanup()
        raise
    except Exception as e:
        print(f"Unexpected error in main: {e}")
        await cleanup()
        raise


if __name__ == "__main__":
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
