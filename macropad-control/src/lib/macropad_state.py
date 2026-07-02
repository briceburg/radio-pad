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

from lib.macropad_keys import VISUAL_MODE_LOADING, VISUAL_MODE_WAITING

PLAYER_STATUS_LEVELS = ("ok", "loading", "warning", "error")
PLAYER_STATUS_SCOPES = ("radio_dial", "switchboard", "playback")
DEGRADED_STATUS_LEVELS = ("warning", "error")


class MacropadState:
    def __init__(self):
        self.player_available = False
        self.station_menu_loaded = False
        self.status_by_scope = {scope: None for scope in PLAYER_STATUS_SCOPES}  # type: dict[str, tuple[str, str | None] | None]

    @property
    def needs_station_menu(self):
        return self.player_available and not self.station_menu_loaded

    def mark_player_available(self):
        if self.player_available:
            return False
        self.player_available = True
        return True

    def mark_player_unavailable(self):
        changed = self.player_available or self.station_menu_loaded or self.has_status
        self.player_available = False
        self.station_menu_loaded = False
        self.clear_statuses()
        return changed

    @property
    def has_status(self):
        return any(self.status_by_scope.values())

    def clear_statuses(self):
        self.status_by_scope = {scope: None for scope in PLAYER_STATUS_SCOPES}

    def handle_event(self, event, keys):
        if not isinstance(event, dict):
            print(f"Unexpected player event: {event}")
            return

        event_name = event.get("event")
        data = event.get("data")

        if event_name == "station_menu":
            self.set_station_menu(data, keys)
        elif event_name == "playback_state":
            self.set_playback_state(data, keys)
        elif event_name == "player_status":
            self.update_status(data)
            self.apply(keys)
        elif event_name != "player_heartbeat":
            print(f"Unknown event: {event}")

    def set_station_menu(self, stations, keys):
        if not isinstance(stations, list) or not all(
            isinstance(call_sign, str) and call_sign for call_sign in stations
        ):
            print(f"Unexpected station_menu payload: {stations}")
            return

        self.station_menu_loaded = True
        keys.set_stations(stations, refresh=False)
        self.apply(keys, force=True)

    def set_playback_state(self, data, keys):
        if not isinstance(data, dict):
            print(f"Unexpected playback_state payload: {data}")
            return
        keys.set_playback_state(
            data.get("call_sign"),
            data.get("requested_call_sign"),
            data.get("failed_call_sign"),
        )

    def update_status(self, data):
        if not isinstance(data, dict):
            print(f"Unexpected player_status payload: {data}")
            return

        scope = data.get("scope")
        level = data.get("level")
        summary = data.get("summary")
        if scope not in self.status_by_scope:
            print(f"Unexpected player_status scope: {scope}")
            return
        if level not in PLAYER_STATUS_LEVELS:
            print(f"Unexpected player_status level: {level}")
            return

        if level == "ok":
            self.status_by_scope[scope] = None
            return

        self.status_by_scope[scope] = (
            level,
            summary if isinstance(summary, str) else None,
        )

    def _status(self, scope):
        return self.status_by_scope[scope] or (None, None)

    def view(self):
        if not self.player_available:
            return False, VISUAL_MODE_WAITING, "Waiting for Player"

        radio_dial_level, radio_dial_summary = self._status("radio_dial")
        switchboard_level, switchboard_summary = self._status("switchboard")
        _, playback_summary = self._status("playback")
        degraded = radio_dial_level in DEGRADED_STATUS_LEVELS or switchboard_level in DEGRADED_STATUS_LEVELS

        if not self.station_menu_loaded:
            return (
                degraded,
                VISUAL_MODE_LOADING,
                playback_summary or radio_dial_summary or switchboard_summary or "Loading RadioDial",
            )

        return degraded, None, playback_summary

    def apply(self, keys, force=False):
        degraded, visual_mode, title_override = self.view()
        keys.set_visual_state(
            degraded=degraded,
            visual_mode=visual_mode,
            title_override=title_override,
            force=force,
        )
