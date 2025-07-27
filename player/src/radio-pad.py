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

import os
import sys
import asyncio
import signal
import traceback
import lib.config as config

from lib.player_mpv import MpvPlayer
from lib.client_switchboard import SwitchboardClient
from lib.client_macropad import MacropadClient

async def cleanup(player):
    print("Cleaning up before exit...")
    await player.stop()
    for client in player.clients:
        try:
            await client.close()
        except Exception as e:
            print(f"Error closing client {client.__class__.__name__}: {e}")

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


if __name__ == "__main__":
    def handle_exit(signum=None, frame=None, code=0):
        print("\nPLAYER: received exit signal...")
        sys.exit(code)

    # Pass all config to discover_config
    player_config = config.make(
        player_id=os.getenv("RADIOPAD_PLAYER_ID", "briceburg"),
        registry_url=os.getenv("RADIOPAD_REGISTRY_URL", "https://registry.radiopad.dev"),
        stations_url=os.getenv("RADIOPAD_STATIONS_URL", None),
        switchboard_url=os.getenv("RADIOPAD_SWITCHBOARD_URL", None),
        enable_discovery=os.getenv("RADIOPAD_ENABLE_DISCOVERY", "true").lower() == "true",
    )

    player = MpvPlayer(player_config, audio_channels=os.getenv("RADIOPAD_AUDIO_CHANNELS", "stereo"))
    # TODO: interface should be player.register_client(MacropadClient(player))??
    macropad_client = MacropadClient(player)
    switchboard_client = SwitchboardClient(player)

    signal.signal(signal.SIGTERM, handle_exit)
    signal.signal(signal.SIGINT, handle_exit)

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
