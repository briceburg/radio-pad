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
import random
from collections.abc import Awaitable, Callable

import websockets

from lib.config import http_client_headers
from lib.interfaces import RadioPadClient, RadioPadPlayer

logger = logging.getLogger("SWITCHBOARD")

MPV_SOCKET_FILE = "/tmp/radio-pad-mpv.sock"
SWITCHBOARD_CONNECT_TIMEOUT_SECONDS = 5
SWITCHBOARD_RETRY_INITIAL_DELAY_SECONDS = 1
SWITCHBOARD_RETRY_FACTOR = 1.5
SWITCHBOARD_RETRY_JITTER_SECONDS = 1
SWITCHBOARD_RETRY_MAX_DELAY_SECONDS = 8


def next_retry_delay(
    retry_delay: float,
    *,
    factor: float = SWITCHBOARD_RETRY_FACTOR,
    jitter_seconds: float = SWITCHBOARD_RETRY_JITTER_SECONDS,
    max_delay_seconds: float = SWITCHBOARD_RETRY_MAX_DELAY_SECONDS,
) -> tuple[float, float]:
    """Return (sleep_seconds, next_delay) with exponential backoff + jitter."""
    sleep_seconds = min(
        retry_delay + (random.random() * jitter_seconds),
        max_delay_seconds,
    )
    next_delay = min(retry_delay * factor, max_delay_seconds)
    return sleep_seconds, next_delay


class SwitchboardClient(RadioPadClient):
    def __init__(
        self,
        player: RadioPadPlayer,
        on_connect: Callable[[], None] | None = None,
        on_disconnect: Callable[[], None] | None = None,
        status_reporter: Callable[[str | None], Awaitable[None]] | None = None,
    ):
        super().__init__(player)
        self.url = player.config.switchboard_url
        self.ws = None
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.status_reporter = status_reporter
        self._connected = False

        self.http_headers = http_client_headers(
            {"RadioPad-Stations-Url": player.config.stations_url}
        )

    async def run(self):
        if not self.url:
            logger.info("skipping switchboard connection, url not provided.")
            return

        retry_delay = SWITCHBOARD_RETRY_INITIAL_DELAY_SECONDS
        while True:
            try:
                await self._connect_and_listen()
                retry_delay = SWITCHBOARD_RETRY_INITIAL_DELAY_SECONDS
            except asyncio.CancelledError:
                raise
            except (ConnectionRefusedError, TimeoutError, OSError) as e:
                logger.warning("failed to connect to %s: %s", self.url, e)
                logger.warning(
                    "If this is the wrong URL, please set the SWITCHBOARD_URL environment variable."
                )
                await self._report_status(self._status_summary(e))
            except websockets.exceptions.WebSocketException as e:
                logger.warning("switchboard websocket error: %s", e)
                await self._report_status(self._status_summary(e))
            except Exception as e:
                logger.error("Unexpected error: %s", e, exc_info=True)

            sleep_seconds, retry_delay = next_retry_delay(retry_delay)
            logger.info("reconnecting to switchboard in %.1fs...", sleep_seconds)
            await asyncio.sleep(sleep_seconds)

    async def _connect_and_listen(self):
        async with websockets.connect(
            self.url,
            additional_headers=self.http_headers,
            open_timeout=SWITCHBOARD_CONNECT_TIMEOUT_SECONDS,
        ) as ws:
            logger.info("connected to: %s", self.url)
            self.ws = ws
            self._connected = True
            if self.on_connect:
                self.on_connect()
            await self._report_status(None)
            asyncio.create_task(self.broadcast("station_playing"))
            async for msg in ws:
                await self.handle_message(msg)
        self.ws = None
        if self._connected:
            self._connected = False
            await self._report_status("Switchboard down")
            if self.on_disconnect:
                self.on_disconnect()

    async def _send(self, message):
        """Send a message to the macropad or switchboard."""
        if self.ws:
            await self.ws.send(message)

    async def _report_status(self, summary):
        if self.status_reporter:
            await self.status_reporter(summary)

    def _status_summary(self, error: Exception) -> str:
        if isinstance(error, ConnectionRefusedError):
            return "Switchboard down"
        if isinstance(error, TimeoutError):
            return "Network timeout"
        return "Network issue"

    async def close(self):
        if self.ws:
            self._connected = False
            await self.ws.close()
