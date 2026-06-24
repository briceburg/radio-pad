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
import json
import logging
import os

import serial.tools.list_ports
import serial_asyncio

from lib.interfaces import RadioPadClient, RadioPadPlayer

logger = logging.getLogger("MACROPAD")

DATA_INTERFACE_NAME = "CircuitPython CDC2"
HEARTBEAT_INTERVAL_SECONDS = 2
PLAYER_STATUS_LEVELS = {"ok", "loading", "warning", "error"}
PLAYER_STATUS_SCOPES = {"upstream", "playback"}


def _candidate_ports():
    configured_port = os.getenv("RADIOPAD_MACROPAD_PORT")
    if configured_port:
        return [configured_port]

    return sorted(
        port.device
        for port in serial.tools.list_ports.comports()
        if port.interface and port.interface.startswith(DATA_INTERFACE_NAME)
    )


class MacropadClient(RadioPadClient):
    def __init__(self, player: RadioPadPlayer):
        super().__init__(player)
        self.writer = None
        self.reader = None
        self._status_by_scope = {}
        self._closed = False

        # Override station_list handler
        self.register_event("station_list", self._handle_station_list)

    async def run(self):
        self._closed = False
        while not self._closed:
            try:
                await self._connect_and_listen()
            except asyncio.CancelledError:
                self._closed = True
                raise
            except Exception as e:
                logger.error("Unexpected error: %s", e, exc_info=True)
            finally:
                await self._close_connection()

            if self._closed:
                return

            logger.debug("checking for macropad in 3s...")
            await asyncio.sleep(3)

    async def _connect(self):
        macropad_ports = _candidate_ports()

        if not macropad_ports:
            logger.debug(
                "no macropad data port found; continuing without local controller"
            )
            return None, None

        if len(macropad_ports) > 1:
            logger.warning(
                "multiple macropad data ports found: %s; set RADIOPAD_MACROPAD_PORT",
                macropad_ports,
            )
            return None, None

        macropad_port = macropad_ports[0]
        logger.info("attempting to connect to %s", macropad_port)
        try:
            reader, writer = await serial_asyncio.open_serial_connection(
                url=macropad_port, baudrate=115200
            )
            logger.info("connected to: %s", macropad_port)
            return reader, writer
        except Exception as e:
            logger.warning("failed to connect to %s: %s", macropad_port, e)
            return None, None

    async def _connect_and_listen(self):
        self.reader, self.writer = await self._connect()

        if not self.writer:
            return

        # Clear pending serial messages
        try:
            while True:
                line = await asyncio.wait_for(self.reader.readline(), timeout=0.1)
                if not line:
                    break
        except asyncio.TimeoutError:
            pass  # Ignore timeout

        await self.resend_status()
        await self._run_session()

    async def _run_session(self):
        listen_task = asyncio.create_task(self._listen())
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        done, pending = await asyncio.wait(
            {listen_task, heartbeat_task}, return_when=asyncio.FIRST_COMPLETED
        )

        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()

    async def _listen(self):
        buffer = ""
        while True:
            try:
                line = await self.reader.readline()
                if not line:
                    break
                buffer += line.decode("utf-8")
                while "\n" in buffer:
                    msg, buffer = buffer.split("\n", 1)
                    msg = msg.strip()
                    if not msg:
                        continue
                    await self.handle_message(msg)
            except Exception as e:
                logger.error("error reading message: %s", e)
                break

    async def _send(self, message: str):
        if self.writer:
            try:
                self.writer.write((message + "\n").encode())
                await self.writer.drain()
            except Exception as e:
                if not self._closed:
                    logger.warning("macropad connection lost while sending: %s", e)
                await self._close_connection()

    async def _close_connection(self):
        writer = self.writer
        self.writer = None
        self.reader = None
        if not writer:
            return

        try:
            close = getattr(writer, "close", None)
            if close:
                close()
            wait_closed = getattr(writer, "wait_closed", None)
            if wait_closed:
                await wait_closed()
        except Exception as e:
            if not self._closed:
                logger.warning("error closing macropad connection: %s", e)

    async def _heartbeat_loop(self):
        while self.writer and not self._closed:
            await self._send(json.dumps({"event": "player_heartbeat", "data": None}))
            if not self.writer:
                return
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

    async def publish_status(self, scope, level="warning", summary=None):
        if scope not in PLAYER_STATUS_SCOPES:
            logger.warning("ignoring invalid macropad status scope: %r", scope)
            return
        if level not in PLAYER_STATUS_LEVELS:
            logger.warning("ignoring invalid macropad status level: %r", level)
            return

        self._status_by_scope[scope] = {
            "level": level,
            "summary": summary if isinstance(summary, str) else None,
        }
        await self.resend_status(scope)

    async def resend_status(self, scope=None):
        if not self.writer:
            return

        scopes = [scope] if scope else sorted(self._status_by_scope)
        for status_scope in scopes:
            status = self._status_by_scope.get(status_scope)
            if not status:
                continue
            await self._send(
                json.dumps(
                    {
                        "event": "player_status",
                        "data": {
                            "scope": status_scope,
                            "level": status["level"],
                            "summary": status["summary"],
                        },
                    }
                )
            )

    async def _handle_station_list(self, event):
        station_list = [station.name for station in self.player.config.stations]
        await self.broadcast("station_list", data=station_list, limit_to_self=True)
        await asyncio.sleep(0.1)  # Handle backpressure
        await self.broadcast("station_playing")
        await asyncio.sleep(0.1)
        await self.resend_status()

    async def close(self):
        self._closed = True
        await self._close_connection()
