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
import signal
import time
import traceback

from lib.player_mpv import MpvPlayer
from lib.client_switchboard import SwitchboardClient
from lib.client_macropad import MacropadClient
from lib.interfaces import RadioPadPlayerConfig


async def cleanup(player):
    print("Cleaning up before exit...")
    player.stop()
    for client in player.clients:
        try:
            await client.close()
        except Exception as e:
            print(f"Error closing client {client.__class__.__name__}: {e}")


def create_player():
    """
    Create and configure a RadioPadPlayer,
    performing registry discovery if needed.
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
    return MpvPlayer(player_config)


# --- Usage in main script ---

if __name__ == "__main__":

    def handle_exit(signum=None, frame=None, code=0):
        print("\nPLAYER: received exit signal...")
        sys.exit(code)

    player = create_player()
    macropad_client = MacropadClient(player)
    switchboard_client = SwitchboardClient(player)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    async def main():
        try:
            client_tasks = [client.run() for client in player.clients]
            await asyncio.gather(*client_tasks)

        except asyncio.CancelledError:
            print("\nexiting...")
            await cleanup(player)
            raise
        except Exception as e:
            print(f"Unexpected error in main: {e}")
            traceback.print_exc()
            await cleanup(player)
            raise

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
