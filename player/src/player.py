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

import asyncio
import logging
import os
import sys

import lib.config as config
from lib.client_macropad import MacropadClient
from lib.client_switchboard import SwitchboardClient
from lib.exceptions import ConfigError
from lib.player_mpv import MpvPlayer

logger = logging.getLogger(__name__)


async def cleanup(player):
    logger.info("Cleaning up before exit...")
    await player.stop()
    for client in player.clients:
        try:
            await client.close()
        except Exception as e:
            logger.error("Error closing client %s: %s", client.__class__.__name__, e)


async def main(player):
    """Runs the main event loop for the radio-pad player."""
    try:
        client_tasks = [client.run() for client in player.clients]
        await asyncio.gather(*client_tasks)

    except asyncio.CancelledError:
        logger.info("exiting...")
        await cleanup(player)
        raise
    except Exception as e:
        logger.critical("Unexpected error in main: %s", e, exc_info=True)
        await cleanup(player)
        raise


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)-8s - %(name)-12s - %(message)s",
        datefmt="%H:%M:%S",
    )

    player = None
    try:
        # Load configuration
        player_config = config.make(
            player_id=os.getenv("RADIOPAD_PLAYER_ID", "briceburg"),
            registry_url=os.getenv(
                "RADIOPAD_REGISTRY_URL", "https://registry.radiopad.dev"
            ),
            stations_url=os.getenv("RADIOPAD_STATIONS_URL", None),
            switchboard_url=os.getenv("RADIOPAD_SWITCHBOARD_URL", None),
            enable_discovery=os.getenv("RADIOPAD_ENABLE_DISCOVERY", "true").lower()
            == "true",
        )

        # Initialize player and clients
        player = MpvPlayer(
            player_config,
            audio_channels=os.getenv("RADIOPAD_AUDIO_CHANNELS", "stereo"),
            socket_path=os.getenv(
                "RADIOPAD_MPV_SOCKET_PATH", "/tmp/radio-pad-mpv.sock"
            ),
        )
        player.register_client(MacropadClient(player))
        player.register_client(SwitchboardClient(player))

        # Run the main event loop
        asyncio.run(main(player))

    except ConfigError as e:
        logger.critical("Configuration error: %s", e)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        # KeyboardInterrupt handles SIGINT (Ctrl+C) and SIGTERM
        logger.info("Application terminated gracefully.")
    except Exception as e:
        logger.critical("Unexpected error: %s", e, exc_info=True)
        sys.exit(1)
