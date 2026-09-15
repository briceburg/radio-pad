# SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import websockets

from lib.config import http_client_headers
from lib.interfaces import RadioPadClient, RadioPadPlayer

logger = logging.getLogger("SWITCHBOARD")


class SwitchboardClient(RadioPadClient):
    def __init__(
        self,
        player: RadioPadPlayer,
        on_connect: Callable[[], None] | None = None,
        on_disconnect: Callable[[], None] | None = None,
        status_reporter: Callable[[str, str | None], Awaitable[None]] | None = None,
        radio_dial_reloader: Callable[[str, str], Awaitable[None]] | None = None,
    ):
        super().__init__(player)
        config = player.config
        if config is None:
            raise RuntimeError("SwitchboardClient requires loaded player configuration")
        if config.radio_dial_revision is None:
            raise RuntimeError("SwitchboardClient requires a RadioDial revision")

        self.url = config.switchboard_url
        self.ws: Any | None = None
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.status_reporter = status_reporter
        self.radio_dial_reloader = radio_dial_reloader
        self._radio_dial_task: asyncio.Task[None] | None = None
        self._connected = False
        self._closing = False

        self.http_headers = http_client_headers(
            {
                "RadioPad-Radio-Dial-Url": config.radio_dial_url,
                "RadioPad-Radio-Dial-Revision": config.radio_dial_revision,
            }
        )
        if radio_dial_reloader:
            self.register_event("radio_dial_state", self._handle_radio_dial_state)

    async def run(self):
        if not self.url:
            logger.info("skipping switchboard connection, url not provided.")
            return

        while True:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                self._closing = True
                raise
            except Exception as e:
                await self._report_status("warning", self._status_summary(e))
                logger.error("Unexpected error: %s", e, exc_info=True)
            logger.info("reconnecting to switchboard in 5s...")
            await asyncio.sleep(5)

    async def _connect_and_listen(self):
        if not self.url:
            return

        async for ws in websockets.connect(self.url, additional_headers=self.http_headers):
            try:
                logger.info("connected to: %s", self.url)
                self.ws = ws
                self._connected = True
                if self.on_connect:
                    self.on_connect()
                await self._report_status("ok", None)
                await self.broadcast("playback_state")
                async for msg in ws:
                    await self.handle_message(msg.decode() if isinstance(msg, bytes) else msg)
            except asyncio.CancelledError:
                self._closing = True
                raise
            except websockets.exceptions.ConnectionClosed:
                # If the connection fails with a transient error, it is retried with exponential backoff. If it fails with a fatal error, the exception is raised, breaking out of the loop.
                continue
            except (ConnectionRefusedError, OSError) as e:
                logger.warning("failed to connect to %s: %s", self.url, e)
                logger.warning(
                    "If this is the wrong URL, please set the RADIOPAD_SWITCHBOARD_URL environment variable."
                )
                await self._report_status("warning", self._status_summary(e))
                continue
            finally:
                self.ws = None
                if self._connected:
                    self._connected = False
                    if self.on_disconnect:
                        self.on_disconnect()
                    if not self._closing:
                        await self._report_status("warning", "Switchboard down")

    async def _send(self, message):
        """Send a message to the macropad or switchboard."""
        if self.ws:
            await self.ws.send(message)

    async def _handle_radio_dial_state(self, event):
        data = event.get("data")
        url = data.get("url") if isinstance(data, dict) else None
        revision = data.get("revision") if isinstance(data, dict) else None
        if not isinstance(url, str) or not isinstance(revision, str):
            logger.warning("ignoring invalid radio_dial_state")
            return
        config = self.player.config
        if config and config.radio_dial_url == url and config.radio_dial_revision == revision:
            return
        if self._radio_dial_task:
            self._radio_dial_task.cancel()
            await asyncio.gather(self._radio_dial_task, return_exceptions=True)
        self._radio_dial_task = asyncio.create_task(
            self._reload_radio_dial(url, revision),
            name="radio-dial-reload",
        )

    async def _reload_radio_dial(self, url, revision):
        if self.radio_dial_reloader:
            await self.radio_dial_reloader(url, revision)
            config = self.player.config
            if config and config.radio_dial_revision:
                self.http_headers["RadioPad-Radio-Dial-Url"] = config.radio_dial_url
                self.http_headers["RadioPad-Radio-Dial-Revision"] = config.radio_dial_revision

    async def _report_status(self, level, summary):
        if self.status_reporter:
            await self.status_reporter(level, summary)

    def _status_summary(self, error):
        if isinstance(error, ConnectionRefusedError):
            return "Switchboard down"
        if isinstance(error, TimeoutError):
            return "Network timeout"
        return "Network issue"

    async def close(self):
        self._closing = True
        if self._radio_dial_task:
            self._radio_dial_task.cancel()
            await asyncio.gather(self._radio_dial_task, return_exceptions=True)
        if self.ws:
            self._connected = False
            await self.ws.close()
