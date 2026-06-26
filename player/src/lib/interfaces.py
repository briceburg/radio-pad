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
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


@dataclass
class RadioPadStation:
    name: str
    url: str


@dataclass
class RadioPadPlayerConfig:
    id: str
    stations_url: str | None
    stations: list[RadioPadStation] = field(default_factory=list)
    registry_url: Optional[str] = None
    switchboard_url: Optional[str] = None


class RadioPadEvent(TypedDict, total=False):
    event: str
    data: Optional[object]


class RadioPadPlayer(abc.ABC):
    """
    Interface for RadioPad player implementations.
    """

    def __init__(self, config: RadioPadPlayerConfig):
        self._station: Optional[RadioPadStation] = None
        self._config: RadioPadPlayerConfig = config
        self._clients: list[RadioPadClient] = []

    @property
    def config(self) -> RadioPadPlayerConfig:
        """Get the player configuration."""
        return self._config

    def update_config(self, config: RadioPadPlayerConfig):
        """Replace the player configuration after discovery succeeds."""
        self._config = config

    @property
    def station(self) -> Optional[RadioPadStation]:
        """Get or set the currently playing station."""
        return self._station

    @station.setter
    def station(self, value: Optional[RadioPadStation]):
        self._station = value

    @property
    def clients(self):
        """Get the list of connected clients (read-only)."""
        return self._clients

    def register_client(self, client):
        """Register a client with this player."""
        self._clients.append(client)

    @abc.abstractmethod
    async def play(self, station: RadioPadStation):
        """Play a radio station and return True when playback starts."""

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
            "client_count",
            "player_presence",
            "player_status",
            "player_heartbeat",
            "station_catalog",
            "station_catalog_url",
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
        if event == "playback_state":
            data = {"station_name": (self.player.station.name if self.player.station else None)}
        message = json.dumps({"event": event, "data": data})
        for client in self.player.clients:
            if limit_to_self and client is not self:
                continue
            try:
                await client._send(message)
            except Exception as e:
                logger.error("Broadcast error for %s: %s", client, e)

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
        station_name = data.get("station_name") if isinstance(data, dict) else None
        if not station_name:
            logger.warning("playback_start missing station_name")
            return

        station = next((s for s in self.player.config.stations if s.name == station_name), None)
        if station:
            await self.player.play(station)
            await self.broadcast("playback_state")
            return

        logger.warning("Station '%s' not found in RADIO_STATIONS.", station_name)

    async def _handle_playback_stop(self, event):
        await self.player.stop()
        await self.broadcast("playback_state")

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
