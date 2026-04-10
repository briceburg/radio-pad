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

import displayio
import terminalio
from adafruit_display_shapes.rect import Rect
from adafruit_display_text import label

from .macropad_keys import MACROPAD_KEY_COUNT

TITLE_MAX_CHARS = 18  # Empirically fits the MacroPad title bar without clipping.
STATION_LABEL_MAX_CHARS = 6  # Keeps 3-column station labels readable on the MacroPad grid.
TITLE_TRUNCATION_SUFFIX = ">"


class MacropadDisplay:
    def __init__(self, macropad):
        self.macropad = macropad
        self.macropad.display.auto_refresh = False
        self._max_text_length = TITLE_MAX_CHARS
        self._group = displayio.Group()

        for group_index in range(MACROPAD_KEY_COUNT):
            x = group_index % 3
            y = group_index // 3
            self._group.append(
                label.Label(
                    terminalio.FONT,
                    text="",
                    color=0xFFFFFF,
                    anchored_position=(
                        (self.macropad.display.width - 1) * x / 2,
                        self.macropad.display.height - 1 - (3 - y) * 12,
                    ),
                    anchor_point=(x / 2, 1.0),
                )
            )

        self._title_bar = Rect(0, 0, self.macropad.display.width, 13, fill=0xFFFFFF)
        self._group.append(self._title_bar)

        self._title_text = label.Label(
            terminalio.FONT,
            text="",
            color=0x000000,
            anchored_position=(self.macropad.display.width // 2, 7),
            anchor_point=(0.5, 0.5),
        )
        self._group.append(self._title_text)

        self.macropad.display.root_group = self._group

    def _normalize_text(self, text):
        if not isinstance(text, str):
            text = "" if text is None else str(text)

        if len(text) <= self._max_text_length:
            return text

        if self._max_text_length <= len(TITLE_TRUNCATION_SUFFIX):
            return text[: self._max_text_length]

        return (
            text[: self._max_text_length - len(TITLE_TRUNCATION_SUFFIX)]
            + TITLE_TRUNCATION_SUFFIX
        )

    def normalize_station_label(self, text):
        if not isinstance(text, str):
            text = "" if text is None else str(text)

        if len(text) <= STATION_LABEL_MAX_CHARS:
            return text

        return text[:STATION_LABEL_MAX_CHARS]

    def set_title(self, text, refresh=True):
        text = self._normalize_text(text)
        if self._title_text.text == text:
            return
        self._title_text.text = text
        if refresh:
            self.refresh()

    def set_group_text(self, group_index, text):
        if 0 <= group_index < MACROPAD_KEY_COUNT:
            self._group[group_index].text = self.normalize_station_label(text)

    def highlight_group(self, group_index):
        if 0 <= group_index < MACROPAD_KEY_COUNT:
            self._group[group_index].color = 0x000000
            self._group[group_index].background_color = 0xFFFFFF

    def unhighlight_group(self, group_index):
        if 0 <= group_index < MACROPAD_KEY_COUNT:
            self._group[group_index].color = 0xFFFFFF
            self._group[group_index].background_color = 0x000000

    def refresh(self):
        self.macropad.display.refresh()
