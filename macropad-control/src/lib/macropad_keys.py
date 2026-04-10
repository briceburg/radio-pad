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

DEFAULT_COLOR = 0x000077
PLAYING_COLOR = 0x015C01
PRESSED_COLOR = 0x999999
MACROPAD_KEY_COUNT = 12
UPSTREAM_WARNING_COLOR = 0x402000
WAITING_ANIMATION_PERIOD = 1.6
WAITING_DISCONNECTED_LED_MAX = 0x40
WAITING_LOADING_LED_MAX = 0x50
WAITING_ROW_PHASE_STEP = 0.12
WAITING_COLUMN_PHASE_STEP = 0.08
WAITING_MODE_DISCONNECTED = "disconnected"
WAITING_MODE_LOADING = "loading"


class MacropadKeys:
    def __init__(self, macropad, display):
        self.macropad = macropad
        self.display = display
        self.macropad.pixels.auto_write = False
        self.macropad.pixels.brightness = 0.10
        self.stations = []
        self.playing_station_index = None
        self.current_page_index = 0
        self.title_override = None
        self.waiting_animation_mode = None
        self.upstream_warning = False
        self._last_animation_tick = 0.0
        self.pages = [{"stations": [], "title": "iCEBURG Radio"}]

    def set_stations(self, stations_list):
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
        self.switch_page(0)

    def switch_page(self, page_index):
        self.current_page_index = page_index
        self.refresh()

    def set_title_override(self, title):
        normalized = title if isinstance(title, str) and title else None
        if self.title_override == normalized:
            return

        self.title_override = normalized
        self.refresh()

    def set_waiting_animation(self, mode):
        normalized = mode if mode in (
            WAITING_MODE_DISCONNECTED,
            WAITING_MODE_LOADING,
        ) else None
        if self.waiting_animation_mode == normalized:
            return

        self.waiting_animation_mode = normalized
        self._last_animation_tick = 0.0
        self.refresh()

    def set_upstream_warning(self, enabled):
        enabled = bool(enabled)
        if self.upstream_warning == enabled:
            return

        self.upstream_warning = enabled
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

        if self.waiting_animation_mode:
            self._animate_waiting_pixels(force=True)

        self.macropad.pixels.show()
        self.display.refresh()

    def tick(self):
        if self.waiting_animation_mode:
            self._animate_waiting_pixels()

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
        if self.upstream_warning:
            return UPSTREAM_WARNING_COLOR
        return station.get("color", DEFAULT_COLOR)

    def _animate_waiting_pixels(self, force=False):
        now = time.monotonic()
        if not force and now - self._last_animation_tick < 0.05:
            return

        self._last_animation_tick = now
        animation_position = (now / WAITING_ANIMATION_PERIOD) % 1.0
        for key_index in range(MACROPAD_KEY_COUNT):
            phase = (
                animation_position
                + (key_index // 3) * WAITING_ROW_PHASE_STEP
                + (key_index % 3) * WAITING_COLUMN_PHASE_STEP
            ) % 1.0
            level = self._triangle_wave(phase)
            self.macropad.pixels[key_index] = self._waiting_animation_color(level)
        self.macropad.pixels.show()

    def _triangle_wave(self, phase):
        if phase < 0.5:
            return phase * 2
        return (1.0 - phase) * 2

    def _waiting_animation_color(self, level):
        if self.waiting_animation_mode == WAITING_MODE_LOADING:
            red = int(WAITING_LOADING_LED_MAX * level)
            green = int((WAITING_LOADING_LED_MAX // 2) * level)
            return (red << 16) | (green << 8)

        grey = int(WAITING_DISCONNECTED_LED_MAX * level)
        return (grey << 16) | (grey << 8) | grey
