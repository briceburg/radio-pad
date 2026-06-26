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

import time

from lib.macropad_time import ticks_diff, ticks_ms

DEFAULT_COLOR = 0x000077
PLAYING_COLOR = 0x015C01
PRESSED_COLOR = 0x999999
MACROPAD_KEY_COUNT = 12
DEGRADED_COLOR = 0x402000
KEY_PIXEL_BRIGHTNESS = 0.08
ENABLE_SKELETON_ANIMATION = True
SKELETON_ANIMATION_TIMEOUT_MS = 10 * 60 * 1000
SKELETON_PERIOD_MS = 1600
SKELETON_TICK_MS = 100
SKELETON_ROW_PHASE_STEP = 0.12
SKELETON_COLUMN_PHASE_STEP = 0.08
SKELETON_LOADING_MAX = 0x40
SKELETON_WAITING_MAX = 0x18
SKELETON_DEGRADED_RED_MAX = 0x40
SKELETON_DEGRADED_GREEN_MAX = 0x20
VISUAL_MODE_LOADING = "loading"
VISUAL_MODE_WAITING = "waiting"


class MacropadKeys:
    def __init__(self, macropad, display):
        self.macropad = macropad
        self.display = display
        self.macropad.pixels.auto_write = False
        self.macropad.pixels.brightness = KEY_PIXEL_BRIGHTNESS
        self.stations = []
        self.playing_station_index = None
        self.current_page_index = 0
        self.degraded = False
        self.title_override = None
        self.visual_mode = None
        self._last_animation_tick = 0
        self._visual_mode_started_at = ticks_ms()
        self._static_skeleton_applied = False
        self.pages = [{"stations": [], "title": "iCEBURG Radio"}]

    def set_stations(self, stations_list, refresh=True):
        self.playing_station_index = None
        self.stations = stations_list
        self.pages = []
        if stations_list:
            for i in range(0, len(stations_list), MACROPAD_KEY_COUNT):
                self.pages.append(
                    {
                        "stations": stations_list[i : i + MACROPAD_KEY_COUNT],
                        "title": (
                            "iCEBURG Radio"
                            if len(stations_list) <= MACROPAD_KEY_COUNT
                            else f"iCEBURG Radio {int(i / MACROPAD_KEY_COUNT) + 1}"
                        ),
                    }
                )
        else:
            self.pages = [{"stations": [], "title": "iCEBURG Radio"}]
        self.switch_page(0, refresh=refresh)

    def switch_page(self, page_index, refresh=True):
        self.current_page_index = page_index
        if refresh:
            self.refresh()

    def set_visual_state(
        self,
        degraded,
        visual_mode,
        title_override,
        force=False,
    ):
        degraded = bool(degraded)
        if visual_mode not in (VISUAL_MODE_LOADING, VISUAL_MODE_WAITING):
            visual_mode = None
        if title_override and not isinstance(title_override, str):
            title_override = str(title_override)
        title_override = title_override or None

        changed = (
            self.degraded != degraded
            or self.visual_mode != visual_mode
            or self.title_override != title_override
        )
        mode_changed = self.visual_mode != visual_mode
        self.degraded = degraded
        self.visual_mode = visual_mode
        self.title_override = title_override

        if mode_changed:
            self._last_animation_tick = 0
            self._visual_mode_started_at = ticks_ms()
            self._static_skeleton_applied = False

        if changed or force:
            self.refresh()

    def refresh(self):
        page = self.pages[self.current_page_index]

        title = self.title_override or page["title"]
        if self.title_override is None and self.playing_station_index is not None:
            station_page_index = self.get_station_page_index(self.playing_station_index)
            if self.current_page_index == station_page_index:
                station_index_on_page = self.playing_station_index % MACROPAD_KEY_COUNT
                title = page["stations"][station_index_on_page].get("name", "?")

        self.display.set_title(title, False)

        for i in range(MACROPAD_KEY_COUNT):
            self.display.unhighlight_group(i)
            if i < len(page["stations"]):
                station = page["stations"][i]
                self.display.set_group_text(i, station.get("name", ""))

                station_global_index = self.current_page_index * MACROPAD_KEY_COUNT + i
                if station_global_index == self.playing_station_index:
                    self.macropad.pixels[i] = PLAYING_COLOR
                    self.display.highlight_group(i)
                else:
                    self.macropad.pixels[i] = self._station_color(station)
            else:
                self.macropad.pixels[i] = 0
                self.display.set_group_text(i, "")

        if self.visual_mode:
            self._animate_skeleton(force=True)

        self.macropad.pixels.show()
        self.display.refresh()

    def tick(self):
        if self.visual_mode:
            self._animate_skeleton()

    def set_key_color(self, key_index, color):
        if 0 <= key_index < MACROPAD_KEY_COUNT:
            self.macropad.pixels[key_index] = color
            self.macropad.pixels.show()

    def set_playing_station(self, station_name):
        self.playing_station_index = None
        if station_name:
            for i, station in enumerate(self.stations):
                if station.get("name") == station_name:
                    self.playing_station_index = i
                    break

        if self.playing_station_index is not None:
            page_index = self.get_station_page_index(self.playing_station_index)
            self.switch_page(page_index)
        else:
            self.refresh()

    def get_station_page_index(self, station_index):
        return station_index // MACROPAD_KEY_COUNT

    def get_station_name(self, key_number):
        page = self.pages[self.current_page_index]
        if key_number < len(page["stations"]):
            return page["stations"][key_number].get("name")
        return None

    def flash_keys(self, color=0x990909, duration=0.88):
        for i in range(MACROPAD_KEY_COUNT):
            self.macropad.pixels[i] = color
        self.macropad.pixels.show()
        time.sleep(duration)
        self.refresh()

    def _station_color(self, station):
        if self.degraded:
            return DEGRADED_COLOR
        return station.get("color", DEFAULT_COLOR)

    def _animate_skeleton(self, force=False):
        now = ticks_ms()
        if (
            not ENABLE_SKELETON_ANIMATION
            or ticks_diff(now, self._visual_mode_started_at)
            >= SKELETON_ANIMATION_TIMEOUT_MS
        ):
            if force or not self._static_skeleton_applied:
                self._set_static_skeleton()
            return

        if not force and ticks_diff(now, self._last_animation_tick) < SKELETON_TICK_MS:
            return

        self._last_animation_tick = now
        self._static_skeleton_applied = False
        animation_position = (now % SKELETON_PERIOD_MS) / SKELETON_PERIOD_MS
        self._set_skeleton(animation_position, animated=True)
        self.macropad.pixels.show()

    def _set_static_skeleton(self):
        self._set_skeleton()
        self.macropad.pixels.show()
        self._static_skeleton_applied = True

    def _set_skeleton(self, offset=0, animated=False):
        for key_index in range(MACROPAD_KEY_COUNT):
            level = self._triangle_wave(self._skeleton_phase(key_index, offset))
            if not animated:
                level = 0.35 + (level * 0.35)
            self.macropad.pixels[key_index] = self._skeleton_color(level)

    def _skeleton_phase(self, key_index, offset=0):
        return (
            offset
            + (key_index // 3) * SKELETON_ROW_PHASE_STEP
            + (key_index % 3) * SKELETON_COLUMN_PHASE_STEP
        ) % 1.0

    def _triangle_wave(self, phase):
        if phase < 0.5:
            return phase * 2
        return (1.0 - phase) * 2

    def _skeleton_color(self, level):
        if self.degraded:
            red = int(SKELETON_DEGRADED_RED_MAX * level)
            green = int(SKELETON_DEGRADED_GREEN_MAX * level)
            return (red << 16) | (green << 8)
        maximum = (
            SKELETON_LOADING_MAX
            if self.visual_mode == VISUAL_MODE_LOADING
            else SKELETON_WAITING_MAX
        )
        grey = int(maximum * level)
        return (grey << 16) | (grey << 8) | grey
