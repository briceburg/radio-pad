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

from lib.macropad_keys import DEFAULT_COLOR, VISUAL_MODE_LOADING, VISUAL_MODE_WAITING

PLAYER_STATUS_LEVELS = ("ok", "loading", "warning", "error")
PLAYER_STATUS_SCOPES = ("upstream", "playback")


class MacropadState:
    def __init__(self):
        self.player_available = False
        self.has_stations = False
        self.status_by_scope = {scope: None for scope in PLAYER_STATUS_SCOPES}

    @property
    def needs_stations(self):
        return self.player_available and not self.has_stations

    def mark_player_available(self):
        if self.player_available:
            return False
        self.player_available = True
        return True

    def mark_player_unavailable(self, keys):
        changed = self.player_available or self.has_stations or self.has_status
        self.player_available = False
        if self.has_stations:
            keys.set_stations([], refresh=False)
        self.has_stations = False
        self.clear_statuses()
        return changed

    @property
    def has_status(self):
        for status in self.status_by_scope.values():
            if status:
                return True
        return False

    def clear_statuses(self):
        for scope in self.status_by_scope:
            self.status_by_scope[scope] = None

    def handle_event(self, event, keys):
        if not isinstance(event, dict):
            print(f"Unexpected player event: {event}")
            return

        event_name = event.get("event")
        data = event.get("data")

        if event_name == "station_list":
            self.set_station_list(data, keys)
        elif event_name == "station_playing":
            keys.set_playing_station(data)
        elif event_name == "player_status":
            self.update_status(data)
            self.apply(keys)
        elif event_name != "player_heartbeat":
            print(f"Unknown event: {event}")

    def set_station_list(self, data, keys):
        if not isinstance(data, list):
            print(f"Unexpected station_list payload: {data}")
            return

        station_list = [
            {"name": station, "color": DEFAULT_COLOR}
            for station in data
            if isinstance(station, str)
        ]
        self.has_stations = bool(station_list)
        keys.set_stations(station_list, refresh=False)
        self.apply(keys, force=True)

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

        self.status_by_scope[scope] = summary if isinstance(summary, str) else None

    def status_summary(self, scope):
        return self.status_by_scope.get(scope)

    def apply(self, keys, force=False):
        upstream_summary = self.status_summary("upstream")
        playback_summary = self.status_summary("playback")

        if not self.player_available:
            keys.set_visual_state(
                degraded=False,
                visual_mode=VISUAL_MODE_WAITING,
                title_override="Waiting for Player",
                force=force,
            )
            return

        if not self.has_stations:
            keys.set_visual_state(
                degraded=bool(upstream_summary),
                visual_mode=VISUAL_MODE_LOADING,
                title_override=playback_summary
                or upstream_summary
                or "Loading stations",
                force=force,
            )
            return

        keys.set_visual_state(
            degraded=bool(upstream_summary),
            visual_mode=None,
            title_override=playback_summary,
            force=force,
        )
