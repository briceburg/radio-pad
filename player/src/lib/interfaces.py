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

import abc
import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypedDict

logger = logging.getLogger(__name__)


@dataclass
class RadioPadStation:
    call_sign: str
    stream_url: str


@dataclass
class RadioPadPlayerConfig:
    radio_dial_url: str
    stations: list[RadioPadStation]
    switchboard_url: str | None = None


class RadioPadEvent(TypedDict, total=False):
    event: str
    data: object | None


class RadioPadPlayer(abc.ABC):
    """Coordinate playback requests and define the audio-backend interface."""

    def __init__(self, config: RadioPadPlayerConfig | None = None):
        self._station: RadioPadStation | None = None
        self._config = config
        self._clients: list[RadioPadClient] = []
        self._playback_revision = 0
        self._desired_station: RadioPadStation | None = None
        self._failed_call_sign: str | None = None
        self._playback_worker: asyncio.Task[None] | None = None
        self._playback_changed = asyncio.Event()
        self._broadcast_lock = asyncio.Lock()
        self.status_reporter: Callable[[str, str | None], Awaitable[None]] | None = None

    @property
    def config(self) -> RadioPadPlayerConfig | None:
        """Get the player configuration."""
        return self._config

    def update_config(self, config: RadioPadPlayerConfig):
        """Replace the player configuration after discovery succeeds."""
        self._config = config

    @property
    def station(self) -> RadioPadStation | None:
        """Get or set the station with confirmed playback."""
        return self._station

    @station.setter
    def station(self, value: RadioPadStation | None):
        self._station = value

    @property
    def requested_call_sign(self) -> str | None:
        """Return the latest station request while it is still in flight."""
        return self._desired_station.call_sign if self._desired_station else None

    @property
    def failed_call_sign(self) -> str | None:
        """Return the station whose latest playback attempt failed."""
        return self._failed_call_sign

    @property
    def clients(self):
        """Get the list of connected clients (read-only)."""
        return self._clients

    def register_client(self, client):
        """Register a client with this player."""
        self._clients.append(client)

    async def broadcast(self, event: str, data: object | None = None, limit_to: "RadioPadClient | None" = None):
        """Broadcast an event to registered local and switchboard clients."""
        async with self._broadcast_lock:
            if event == "playback_state":
                data = {
                    "call_sign": self.station.call_sign if self.station else None,
                    "requested_call_sign": self.requested_call_sign,
                    "failed_call_sign": self.failed_call_sign,
                }
            message = json.dumps({"event": event, "data": data})
            for client in self.clients:
                if limit_to is not None and client is not limit_to:
                    continue
                try:
                    await client._send(message)
                except Exception as e:
                    logger.error("Broadcast error for %s: %s", client, e)

    async def request_playback(self, station: RadioPadStation):
        """Set the desired station; duplicate requests are idempotent."""
        duplicate_request = self.requested_call_sign == station.call_sign or (
            self._playback_worker is None and self.station is not None and self.station.call_sign == station.call_sign
        )
        if not duplicate_request:
            self._set_desired_station(station)
        await self.broadcast("playback_state")

    async def reject_playback_request(self, call_sign: str):
        """Report a rejected call sign without disturbing accepted playback."""
        await self._report_status("error", f"Station {call_sign} unavailable")
        await self.broadcast("playback_state")

    async def request_stop(self):
        """Replace any earlier start request with a stop request."""
        self._failed_call_sign = None
        stop_in_flight = self._desired_station is None and self._playback_worker is not None
        already_stopped = self._playback_worker is None and self.station is None
        if not (stop_in_flight or already_stopped):
            self._set_desired_station(None)
        await self.broadcast("playback_state")

    async def wait_for_playback_idle(self):
        """Wait until the latest requested playback state has settled."""
        while self._playback_worker:
            await asyncio.shield(self._playback_worker)

    def _set_desired_station(self, station: RadioPadStation | None):
        # These mutations contain no await, so the event loop applies each request atomically.
        self._playback_revision += 1
        self._desired_station = station
        self._failed_call_sign = None
        self._playback_changed.set()
        if self._playback_worker is None or self._playback_worker.done():
            self._playback_worker = asyncio.create_task(
                self._reconcile_playback(),
                name="playback-worker",
            )

    async def _reconcile_playback(self):
        """Move the backend toward the latest desired station until state settles."""
        try:
            while True:
                revision = self._playback_revision
                station = self._desired_station
                had_confirmed_playback = self.station is not None
                self._playback_changed.clear()

                try:
                    await self.stop()
                except Exception:
                    logger.error("Unexpected error while replacing playback", exc_info=True)
                    self.station = None
                    await self._report_status("error", "Playback error")
                    if not self._clear_request(revision):
                        continue
                    await self.broadcast("playback_state")
                    if self._is_current(revision):
                        return
                    continue
                if not self._is_current(revision):
                    continue
                await self._report_status("ok", None)
                if not self._is_current(revision):
                    continue
                if had_confirmed_playback:
                    await self.broadcast("playback_state")
                    if not self._is_current(revision):
                        continue

                if station is None:
                    if self._clear_request(revision):
                        return
                    continue

                play_task = asyncio.create_task(self.play(station), name=f"playback:{station.call_sign}")
                changed_task = asyncio.create_task(self._playback_changed.wait(), name="playback-changed")
                done, _ = await asyncio.wait({play_task, changed_task}, return_when=asyncio.FIRST_COMPLETED)

                if changed_task in done:
                    play_task.cancel()
                    await asyncio.gather(play_task, return_exceptions=True)
                    continue

                changed_task.cancel()
                await asyncio.gather(changed_task, return_exceptions=True)
                try:
                    success = play_task.result()
                except Exception:
                    logger.error("Unexpected playback error for %s", station.call_sign, exc_info=True)
                    success = False
                    await self._report_status("error", "Playback error")

                if not self._is_current(revision):
                    continue
                if not success:
                    self.station = None
                    self._failed_call_sign = station.call_sign
                if not self._clear_request(revision):
                    continue
                await self.broadcast("playback_state")
                if self._is_current(revision):
                    return
        finally:
            if self._playback_worker is asyncio.current_task():
                self._playback_worker = None

    def _is_current(self, revision: int) -> bool:
        return revision == self._playback_revision

    def _clear_request(self, revision: int) -> bool:
        if not self._is_current(revision):
            return False
        self._desired_station = None
        return True

    async def _report_status(self, level: str, summary: str | None):
        if self.status_reporter:
            try:
                await self.status_reporter(level, summary)
            except Exception:
                logger.error("Playback status reporting failed", exc_info=True)

    @abc.abstractmethod
    async def play(self, station: RadioPadStation):
        """Return True after the backend confirms usable audio for a station."""

    @abc.abstractmethod
    async def stop(self):
        """Stop playback of the current station."""

    @abc.abstractmethod
    async def volume_up(self):
        """Increase the volume."""

    @abc.abstractmethod
    async def volume_down(self):
        """Decrease the volume."""


class RadioPadClient(abc.ABC):
    """
    Interface for RadioPad clients (e.g., MacroPadClient, SwitchboardClient).
    """

    def __init__(self, player: RadioPadPlayer):
        self._player = player
        self._event_handlers: dict[str, Callable[[RadioPadEvent], Awaitable[None]]] = {}
        self.register_event("playback_start", self._handle_playback_start)
        self.register_event("playback_stop", self._handle_playback_stop)
        self.register_event("volume_up", self._handle_volume_up)
        self.register_event("volume_down", self._handle_volume_down)
        # Ignored events
        for ignored in (
            "playback_state",
            "player_presence",
            "player_status",
        ):
            self.register_event(ignored, self._handle_ignored)

    @property
    def player(self) -> RadioPadPlayer:
        """Get the player instance."""
        return self._player

    def register_event(self, event_name: str, handler):
        """Register or override a handler for a specific event."""
        self._event_handlers[event_name] = handler

    async def broadcast(self, event, data=None, limit_to_self=False):
        """Broadcast an event to clients registered with the player."""
        await self.player.broadcast(event, data, limit_to=self if limit_to_self else None)

    async def handle_message(self, message: str):
        """Handle incoming messages."""
        try:
            event = json.loads(message)
            await self.handle_event(event)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Invalid message received: %s", message)
        except Exception:
            logger.error("Error handling message: %s", message, exc_info=True)

    async def handle_event(self, event: RadioPadEvent):
        """Dispatch event to registered handler, fallback to unknown."""
        if not (isinstance(event, dict) and "event" in event):
            raise ValueError("Invalid event structure")
        event_name = event.get("event")
        if not isinstance(event_name, str):
            raise ValueError("Invalid event name")
        handler = self._event_handlers.get(event_name, self._handle_unknown)
        await handler(event)

    async def _handle_volume_up(self, event):
        await self.player.volume_up()

    async def _handle_volume_down(self, event):
        await self.player.volume_down()

    async def _handle_playback_start(self, event):
        data = event.get("data")
        call_sign = data.get("call_sign") if isinstance(data, dict) else None
        if not call_sign:
            logger.warning("playback_start missing call_sign")
            return

        config = self.player.config
        if config is None:
            logger.warning("playback_start received before player configuration loaded")
            return

        station = next((station for station in config.stations if station.call_sign == call_sign), None)
        if station:
            await self.player.request_playback(station)
            return

        logger.warning("Station %r is not on the loaded RadioDial", call_sign)
        await self.player.reject_playback_request(str(call_sign))

    async def _handle_playback_stop(self, event):
        await self.player.request_stop()

    async def _handle_ignored(self, event):
        pass  # Ignore these events

    async def _handle_unknown(self, event):
        logger.warning("%s: unknown event: %s", self.__class__.__name__, event["event"])

    @abc.abstractmethod
    async def run(self):
        """Continuously try to connect and listen for messages."""

    @abc.abstractmethod
    async def _send(self, message: str):
        """Send a message to the macropad or switchboard."""

    @abc.abstractmethod
    async def close(self):
        """Close the client connection."""
