# SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
# SPDX-License-Identifier: GPL-3.0-or-later

import displayio
import terminalio
from adafruit_display_shapes.rect import Rect
from adafruit_display_text import label

from .macropad_keys import MACROPAD_KEY_COUNT

TITLE_MAX_CHARS = 18
STATION_LABEL_MAX_CHARS = 6
TRUNCATION_SUFFIX = ">"


class MacropadDisplay:
    def __init__(self, macropad):
        self.macropad = macropad
        self.macropad.display.auto_refresh = False
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

    def _normalize_text(self, text, max_chars):
        if not isinstance(text, str):
            text = "" if text is None else str(text)

        if len(text) <= max_chars:
            return text

        if max_chars <= len(TRUNCATION_SUFFIX):
            return text[:max_chars]

        return text[: max_chars - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX

    def set_title(self, text, refresh=True):
        text = self._normalize_text(text, TITLE_MAX_CHARS)
        if self._title_text.text == text:
            return
        self._title_text.text = text
        if refresh:
            self.refresh()

    def set_group_text(self, group_index, text):
        if 0 <= group_index < MACROPAD_KEY_COUNT:
            self._group[group_index].text = self._normalize_text(text, STATION_LABEL_MAX_CHARS)

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
